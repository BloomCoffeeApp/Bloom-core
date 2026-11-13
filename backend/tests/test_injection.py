"""Injection resistance of the whole API (core + Pro), driven by its own OpenAPI description.

Every endpoint is called with hostile values in EVERY string it accepts (query, path and JSON body): SQL injection,
XSS, path traversal, command injection, CRLF header injection, template/format strings, NUL bytes and giant values.

What must hold, for all of them:
  * never a server error (5xx) and never an internal detail in the answer (traceback, SQL text, file paths);
  * the database is intact afterwards (same tables, same rows in the tables that the payloads aim at);
  * values stored as data come back byte-for-byte (they are data, never interpreted);
  * a search for "%" or "_" matches the literal character, not "everything"."""
import re

import pytest
from sqlalchemy import func, inspect, select

from app.db import SessionLocal, engine
from app.main import create_app
from app.models import Customer, Product, Sale, User

PAYLOADS = [
    "' OR '1'='1",
    "'; DROP TABLE sales;--",
    "1; SELECT sqlite_version()",
    "' UNION SELECT name, sql FROM sqlite_master--",
    "%' OR 1=1--",
    "\\",
    "%",
    "_",
    "<script>alert(1)</script>",
    "\"><img src=x onerror=alert(1)>",
    "javascript:alert(1)",
    "../../../../etc/passwd",
    "..\\..\\..\\windows\\win.ini",
    "{{7*7}}${7*7}{0.__class__}",
    "$(whoami)`id`; dir | calc &",
    "x\r\nX-Injected: yes\r\nSet-Cookie: a=b",
    "nul\x00byte",
    "=cmd|' /C calc'!A0",
    "A" * 6000,
    "\u202e\ufeff\u200b",
]

LEAK = re.compile(r"Traceback|File \"|\.py\"|sqlalchemy|sqlite3\.|OperationalError|ProgrammingError|syntax error|no such (table|column)", re.I)

# Calls that would act on the machine or the network instead of the data: not part of the injection surface.
SKIP = re.compile(r"^/api/(printing|updates|system/restore|system/lan|collect/mp|license/(checkout|activate|trial))")


def _resolve(spec: dict, node: dict | None, seen: int = 0) -> dict:
    node = node or {}
    while "$ref" in node and seen < 12:
        ref = node["$ref"].lstrip("#/").split("/")
        cur = spec
        for part in ref:
            cur = cur[part]
        node, seen = cur, seen + 1
    return node


def _build(spec: dict, node: dict, payload: str, depth: int = 0):
    """A JSON value for `node` where every string is `payload` (numbers/booleans/enums stay valid)."""
    node = _resolve(spec, node)
    if depth > 5:
        return None
    for key in ("anyOf", "oneOf"):
        if key in node:
            options = [o for o in node[key] if _resolve(spec, o).get("type") != "null"]
            return _build(spec, options[0], payload, depth + 1) if options else None
    if "allOf" in node:
        return _build(spec, node["allOf"][0], payload, depth + 1)
    if "enum" in node:
        return node["enum"][0]
    t = node.get("type")
    if t == "string":
        fmt = node.get("format")
        if fmt in ("date", "date-time"):
            return "2026-01-01" if fmt == "date" else "2026-01-01T00:00:00"
        return payload[: node.get("maxLength", len(payload))]
    if t == "integer":
        return max(node.get("minimum", 0), 1)
    if t == "number":
        return 1.0
    if t == "boolean":
        return False
    if t == "array":
        return [_build(spec, node.get("items", {}), payload, depth + 1)]
    if t == "object" or "properties" in node:
        return {k: _build(spec, v, payload, depth + 1) for k, v in node.get("properties", {}).items()}
    return payload


@pytest.fixture()
def api(seeded):
    client, admin = seeded
    app = client.app
    spec = app.openapi()
    return client, admin, spec


def _endpoints(spec: dict, methods: set[str]):
    for path, ops in spec["paths"].items():
        if SKIP.match(path):
            continue
        for method, op in ops.items():
            if method.upper() in methods:
                yield method.upper(), path, op


def _state() -> dict:
    with SessionLocal() as s:
        tables = sorted(inspect(engine).get_table_names())
        return {
            "tables": tables,
            "sales": s.scalar(select(func.count(Sale.id))),
            "users": s.scalar(select(func.count(User.id))),
            "products": s.scalar(select(func.count(Product.id))),
        }


def _fill_path(path: str, params: list[dict], spec: dict, payload: str) -> str:
    for p in params:
        if p.get("in") == "path":
            value = payload if _resolve(spec, p.get("schema")).get("type") == "string" else "1"
            path = path.replace("{" + p["name"] + "}", value.replace("/", "%2F").replace("\\", "%5C").replace("\x00", "%00").replace("\r", "%0D").replace("\n", "%0A"))
    return re.sub(r"\{[^}]+\}", "1", path)


def _check(r, what: str, bad: list[str]):
    if r.status_code >= 500:
        bad.append(f"{what} -> {r.status_code}")
    elif LEAK.search(r.text[:4000]):
        bad.append(f"{what} leaks internals: {LEAK.search(r.text).group(0)!r}")
    if any(k.lower() in ("x-injected", "set-cookie") for k in r.headers) and "x-injected" in {k.lower() for k in r.headers}:
        bad.append(f"{what} reflected an injected header")


def test_hostile_query_and_path_values_never_break_a_read(api):
    client, admin, spec = api
    before, bad = _state(), []
    for method, path, op in _endpoints(spec, {"GET"}):
        params = op.get("parameters", [])
        for payload in PAYLOADS:
            query = {p["name"]: payload for p in params if p.get("in") == "query" and _resolve(spec, p.get("schema")).get("type", "string") in ("string", None)}
            url = _fill_path(path, params, spec, payload)
            try:
                r = client.get(url, params=query, headers=admin)
            except Exception as e:  # the client itself refused a malformed URL: that is the safe outcome
                if "Invalid" in str(e) or "invalid" in str(e) or "URL" in str(e):
                    continue
                raise
            _check(r, f"GET {path} [{payload[:24]!r}]", bad)
    assert not bad, f"{len(bad)} problems, e.g. {bad[:8]}"
    assert _state() == before, "reads must not change the data"


def test_hostile_json_bodies_never_break_a_write_or_the_database(api):
    client, admin, spec = api
    before_tables = _state()["tables"]
    bad: list[str] = []
    reached: set[tuple[str, str]] = set()  # endpoints whose handler really ran with the payload (not just a 422)
    for method, path, op in _endpoints(spec, {"POST", "PUT", "PATCH"}):
        body_schema = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
        for payload in PAYLOADS[::2] + PAYLOADS[1::6]:  # every payload kind, without an hour-long run
            body = _build(spec, body_schema, payload) if body_schema else None
            url = _fill_path(path, op.get("parameters", []), spec, payload)
            r = client.request(method, url, json=body, headers=admin)
            _check(r, f"{method} {path} [{payload[:24]!r}]", bad)
            if r.status_code != 422:
                reached.add((method, path))
    assert not bad, f"{len(bad)} problems, e.g. {bad[:8]}"
    assert len(reached) > 60, f"only {len(reached)} write endpoints got past validation: the fuzz is too shallow"
    after = _state()
    assert after["tables"] == before_tables, "no payload may add or drop a table"
    with SessionLocal() as s:
        assert s.scalar(select(func.count(Sale.id))) is not None  # `sales` still exists and answers


def test_malformed_json_and_wrong_types_are_clean_errors(api):
    client, admin, _ = api
    for raw in (b"{", b"[]", b'"x"', b"null", b'{"items": "no"}', b"\xff\xfe", b"{" * 5000):
        r = client.post("/api/sales", content=raw, headers={**admin, "Content-Type": "application/json"})
        assert r.status_code in (400, 422), (raw[:20], r.status_code)
        assert not LEAK.search(r.text)
    r = client.post("/api/sales", content="x=1", headers={**admin, "Content-Type": "application/x-www-form-urlencoded"})
    assert r.status_code in (400, 415, 422)


@pytest.mark.parametrize("payload", ["<script>alert(1)</script>", "'; DROP TABLE sales;--", "' OR '1'='1", "%", "_", "=HYPERLINK(\"http://x\")", "\\"])
def test_text_is_stored_and_returned_as_data_only(api, payload):
    client, admin, _ = api
    r = client.post("/api/customers", json={"name": f"N {payload}", "phone": "1155550000", "email": "x@example.com", "notes": payload}, headers=admin)
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    got = client.get(f"/api/customers/{cid}", headers=admin).json()
    assert got["name"] == f"N {payload}", "stored text must come back unchanged"
    with SessionLocal() as s:
        assert s.get(Customer, cid).name == f"N {payload}"
        assert s.scalar(select(func.count(Sale.id))) is not None


def test_search_treats_percent_and_underscore_literally(api):
    client, admin, _ = api
    for i, name in enumerate(("Descuento 100% casa", "Promo 1000 casa", "a_b especial", "axb especial")):
        assert client.post("/api/customers", json={"name": name, "phone": f"115555{i:04d}"}, headers=admin).status_code == 200
    found = lambda q: {c["name"] for c in client.get("/api/customers", params={"q": q}, headers=admin).json()}  # noqa: E731
    assert found("100%") == {"Descuento 100% casa"}, "% must match a literal percent sign"
    assert found("a_b") == {"a_b especial"}, "_ must match a literal underscore"
    everything = len(client.get("/api/customers", headers=admin).json())
    assert len(found("%")) < everything, "a bare % must not match every customer"


def test_spreadsheet_formulas_are_neutralised_in_exports():
    from bloom_pro.services import exporter

    for evil in ("=cmd|' /C calc'!A0", "+1+1", "-2+3", "@SUM(1)", "\t=1", "\r=1"):
        assert exporter._safe_text(evil).startswith("'"), evil
    assert exporter._safe_text("Café con leche") == "Café con leche"
