"""Access matrix: WHO can call WHAT, for every endpoint, derived from the real route table.

The route table is walked (core + Pro) and each endpoint is classified by the dependencies it declares:
public | auth (any logged-in user) | admin | permissions (any of) | legacy role names. Then:

1. NEW ENDPOINTS: a route with no authentication must be listed in PUBLIC below, with the reason. A forgotten
   `Depends(...)` on a new endpoint fails here instead of reaching a customer.
2. NO SESSION: every protected endpoint answers 401 without a token or with a bad one.
3. DENIED: every built-in role is refused (403) on every endpoint whose permissions it lacks. Denial happens before
   the handler runs, so this probes ALL methods safely.
4. ALLOWED: for safe (GET) endpoints, a role that has the permission is NOT refused (not 401/403).

The expected access comes from `app/permissions.py` (the catalog), not from the route code under test.

5. SNAPSHOT: the rule of every endpoint (public / auth / admin / which permissions) is compared with the approved
   `access_rules.snapshot.json`. Weakening a permission, opening an endpoint or adding one changes the snapshot, so
   it fails until the change is approved ON PURPOSE (and reviewed in the diff of that file):

       BLOOM_UPDATE_ACCESS=1 python -m pytest tests/test_access_matrix.py"""
import json
import os
import re
from pathlib import Path

import pytest

from app import permissions
from app.auth import get_current_user, require_admin
from app.main import create_app
from tests.conftest import login

# Endpoints that must work WITHOUT a session. Anything not matching here needs authentication.
PUBLIC: list[tuple[str, str]] = [
    (r"^/api/health$", "liveness probe"),
    (r"^/api/setup(/.*)?$", "first-run setup (refuses once configured)"),
    (r"^/api/auth/(users|login)$", "PIN login screen: user list and login (throttled)"),
    (r"^/api/auth/logout$", "logout reads its own bearer token and is harmless without one"),
    (r"^/api/business/catalog$", "business-profile catalog for the first-run wizard (static text, no data)"),
    (r"^/api/staff/clock$", "time clock by PIN without a session (shares the login throttle)"),
    (r"^/api/team/(users|status)$", "staff phone app: staff list / code check, both behind the team code from the register QR (throttled per IP)"),
    (r"^/api/public/.*$", "customer-facing menu/pickup/screens: token-protected or read-only by design"),
    (r"^/(?!api/).*$", "front-end routes and static files"),
]


def _iter_routes(routes, prefix="", inherited=()):
    for r in routes:
        if type(r).__name__ == "_IncludedRouter":
            ctx = r.include_context
            yield from _iter_routes(r.original_router.routes, prefix + (ctx.prefix or ""), inherited + tuple(ctx.dependencies or ()))
        elif hasattr(r, "dependant"):
            yield prefix + r.path, r, inherited


def _closure(fn, name):
    for var, cell in zip(fn.__code__.co_freevars, fn.__closure__ or ()):
        if var == name:
            return tuple(cell.cell_contents)
    return ()


def _walk(dep):
    for d in dep.dependencies:
        yield d.call
        yield from _walk(d)


def classify(route, inherited) -> dict:
    calls = list(_walk(route.dependant)) + [d.dependency for d in tuple(getattr(route, "dependencies", ())) + inherited]
    info = {"auth": False, "admin": False, "perms": [], "roles": []}
    for c in calls:
        if c is get_current_user:
            info["auth"] = True
        elif c is require_admin:
            info["auth"] = info["admin"] = True
        elif getattr(c, "__qualname__", "") == "require_permission.<locals>._dep":
            info["auth"] = True
            info["perms"].append(_closure(c, "perms"))
        elif getattr(c, "__qualname__", "") == "require_role.<locals>._dep":
            info["auth"] = True
            info["roles"].append(_closure(c, "roles"))
    return info


def _ok(have, info: dict, role: str = "") -> bool:
    """Would a user holding exactly the permissions `have` (and role key `role`) pass this endpoint?"""
    if info["admin"]:
        return False
    if info["roles"] and not all(role in names for names in info["roles"]):
        return False
    return all(any(p in have for p in group) for group in info["perms"])


def _allowed(role: str, info: dict) -> bool:
    """Expected outcome from the permission catalog (admin passes everything)."""
    if role == permissions.ADMIN:
        return True
    return _ok(permissions.BUILTIN_ROLES[role]["permissions"], info, role)


def _public(path: str) -> bool:
    return any(re.match(pat, path) for pat, _ in PUBLIC)


def _endpoints():
    app = create_app(run_lifespan=False)
    out = []
    for path, route, inherited in _iter_routes(app.routes):
        for method in sorted(route.methods or ()):
            if method in ("HEAD", "OPTIONS"):
                continue
            out.append((method, path, classify(route, inherited)))
    return out


ENDPOINTS = _endpoints()
ROLES = list(permissions.BUILTIN_ROLES)  # admin, encargado, cajero, barista, mozo, cocina, deposito


def _fill(path: str) -> str:
    # `{user_id}` is a user nobody has: id 1 is the admin and rank rules (not permissions) would answer 403 for
    # everyone below them, which says nothing about the permission this matrix is checking.
    return re.sub(r"\{[^}]+\}", "1", path.replace("{user_id}", "999999"))


def _body(method: str):
    return {} if method in ("POST", "PUT", "PATCH") else None


def test_the_route_walker_finds_the_api():
    protected = [e for e in ENDPOINTS if e[2]["auth"]]
    assert len(ENDPOINTS) > 250 and len(protected) > 200, (len(ENDPOINTS), len(protected))
    assert any(e[2]["admin"] for e in ENDPOINTS) and any(e[2]["perms"] for e in ENDPOINTS)


def test_every_endpoint_without_authentication_is_a_declared_public_one():
    open_ = sorted(f"{m} {p}" for m, p, info in ENDPOINTS if not info["auth"] and not _public(p))
    assert not open_, ("endpoints with no authentication that are not in PUBLIC (add auth, or list them with the reason): "
                       + "; ".join(open_))


def test_protected_endpoints_answer_401_without_a_valid_session(seeded):
    client, _ = seeded
    bad = []
    for method, path, info in ENDPOINTS:
        if not info["auth"]:
            continue
        for headers in ({}, {"Authorization": "Bearer nope"}):
            r = client.request(method, _fill(path), headers=headers, json=_body(method))
            if r.status_code != 401:
                bad.append(f"{method} {path} -> {r.status_code}")
    assert not bad, bad[:15]


@pytest.fixture()
def tokens(seeded):
    client, admin = seeded
    pins = {"cajero": ("Caja Demo", "1111"), "barista": ("Barista Demo", "2222"), "encargado": ("Encargado Demo", "3333")}
    out = {"admin": admin}
    for role in ROLES:
        if role == "admin":
            continue
        name, pin = pins.get(role, (f"Rol {role}", "4444"))
        if role not in pins:
            r = client.post("/api/users", json={"name": name, "pin": pin, "role": role}, headers=admin)
            assert r.status_code == 200, r.text
        out[role] = login(client, name, pin)
    return client, out


def test_roles_are_refused_where_the_catalog_says_they_lack_permission(tokens):
    client, hdr = tokens
    wrong = []
    checked = 0
    for method, path, info in ENDPOINTS:
        if not info["auth"]:
            continue
        for role in ROLES:
            if _allowed(role, info):
                continue
            r = client.request(method, _fill(path), headers=hdr[role], json=_body(method))
            checked += 1
            if r.status_code != 403:
                wrong.append(f"{role} {method} {path} -> {r.status_code}")
    assert checked > 500, checked
    assert not wrong, f"{len(wrong)} role/endpoint pairs that should be 403: {wrong[:15]}"


def test_roles_with_permission_are_not_refused_on_safe_endpoints(tokens):
    client, hdr = tokens
    wrong = []
    for method, path, info in ENDPOINTS:
        if method != "GET" or not info["auth"]:
            continue
        for role in ROLES:
            if not _allowed(role, info):
                continue
            r = client.request("GET", _fill(path), headers=hdr[role])
            if r.status_code in (401, 403):
                wrong.append(f"{role} GET {path} -> {r.status_code}")
    assert not wrong, f"allowed by the catalog but refused: {wrong[:15]}"


SNAPSHOT = Path(__file__).with_name("access_rules.snapshot.json")


def rule_of(path: str, info: dict) -> str:
    if not info["auth"]:
        return "public"
    parts = []
    if info["admin"]:
        parts.append("admin")
    parts += ["perm:" + "|".join(sorted(g)) for g in info["perms"]]
    parts += ["role:" + "|".join(sorted(g)) for g in info["roles"]]
    return "+".join(parts) or "auth"


def test_access_rules_match_the_approved_snapshot():
    live = {f"{m} {p}": rule_of(p, info) for m, p, info in ENDPOINTS}
    if os.environ.get("BLOOM_UPDATE_ACCESS"):
        SNAPSHOT.write_text(json.dumps(dict(sorted(live.items())), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    approved = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    added = sorted(set(live) - set(approved))
    removed = sorted(set(approved) - set(live))
    changed = sorted(f"{k}: {approved[k]} -> {live[k]}" for k in set(live) & set(approved) if live[k] != approved[k])
    assert not (added or removed or changed), (
        "the access rules changed. If intended, approve with BLOOM_UPDATE_ACCESS=1 and review the diff of "
        f"access_rules.snapshot.json.\n  new: {added[:10]}\n  removed: {removed[:10]}\n  changed: {changed[:10]}"
    )


# ----------------------------------------------------------------------- custom roles and personal exceptions


def _closure(perm: str) -> set[str]:
    out = {perm}
    while perm in permissions.REQUIRES:
        perm = permissions.REQUIRES[perm]
        out.add(perm)
    return out


def _check_user(client, headers, have, role_key: str = "") -> list[str]:
    """Every endpoint must refuse (403) what `have` does not allow and not refuse what it allows (safe GETs)."""
    wrong = []
    for method, path, info in ENDPOINTS:
        if not info["auth"]:
            continue
        allowed = _ok(have, info, role_key)
        if not allowed:
            r = client.request(method, _fill(path), headers=headers, json=_body(method))
            if r.status_code != 403:
                wrong.append(f"{method} {path} -> {r.status_code} (should be 403)")
        elif method == "GET":
            r = client.get(_fill(path), headers=headers)
            if r.status_code in (401, 403):
                wrong.append(f"GET {path} -> {r.status_code} (should be allowed)")
    return wrong


def test_a_custom_role_with_one_permission_gets_exactly_that_access(seeded):
    """For EVERY permission in the catalog: a custom role holding only it (plus what it requires) opens exactly the
    endpoints that need it and nothing else. This is what the owner builds in Configuración → Roles."""
    client, admin = seeded
    wrong = []
    for perm in permissions.PERMISSIONS:
        r = client.post("/api/roles", json={"name": f"Solo {perm}"[:40], "permissions": [perm]}, headers=admin)
        assert r.status_code == 200, (perm, r.text)
        key = r.json()["key"]
        have = set(r.json()["permissions"])
        assert have == _closure(perm), f"role for {perm} got {sorted(have)}, expected {sorted(_closure(perm))}"
        name = f"Usuario {perm}"[:40]
        u = client.post("/api/users", json={"name": name, "pin": "5555", "role": key}, headers=admin)
        assert u.status_code == 200, u.text
        wrong += [f"[{perm}] {w}" for w in _check_user(client, login(client, name, "5555"), have, key)]
    assert not wrong, f"{len(wrong)} mismatches, e.g. {wrong[:10]}"


def test_personal_exceptions_change_exactly_the_endpoints_they_should(seeded):
    client, admin = seeded
    users = client.get("/api/users", headers=admin).json()
    cashier = next(u for u in users if u["name"] == "Caja Demo")
    base = set(permissions.BUILTIN_ROLES["cajero"]["permissions"])

    # 1) take pos.sell away from a cashier: everything that depends on selling closes with it
    r = client.put(f"/api/users/{cashier['id']}/permissions", json={"grants": [], "revokes": ["pos.sell"]}, headers=admin)
    assert r.status_code == 200, r.text
    have = set(r.json()["effective_permissions"])
    assert "pos.sell" not in have and "pos.discount" not in have, "dependants of a revoked permission must go too"
    assert not _check_user(client, login(client, "Caja Demo", "1111"), have, "cajero")

    # 2) give the same cashier stock adjustments (it needs stock.view, which the editor adds)
    r = client.put(f"/api/users/{cashier['id']}/permissions", json={"grants": ["stock.adjust"], "revokes": []}, headers=admin)
    assert r.status_code == 200, r.text
    have = set(r.json()["effective_permissions"])
    assert {"stock.adjust", "stock.view"} <= have and base <= have
    assert not _check_user(client, login(client, "Caja Demo", "1111"), have, "cajero")

    # 3) administrators accept no exceptions
    admin_user = next(u for u in users if u["role"] == "admin")
    r = client.put(f"/api/users/{admin_user['id']}/permissions", json={"grants": [], "revokes": ["pos.sell"]}, headers=admin)
    assert r.status_code in (400, 403, 409, 422), "an administrator must not lose permissions"
