"""HTTP-level security basics that a scanner (OWASP ZAP) would flag first: response headers, CORS, and error bodies
that must never leak internals. Cheap, runs in the normal suite."""
import re

import pytest

EVIL = "http://evil.example"


def test_security_headers_on_api_and_pages(seeded):
    client, admin = seeded
    for path, headers in (("/api/health", {}), ("/api/system/info", admin), ("/", {})):
        r = client.get(path, headers=headers)
        assert r.headers.get("x-content-type-options") == "nosniff", path
        assert r.headers.get("x-frame-options") == "DENY", path  # no clickjacking: the app is never framed
        assert r.headers.get("referrer-policy") == "no-referrer", path


def test_cors_never_allows_a_foreign_origin(seeded):
    client, admin = seeded
    for method in ("GET", "POST", "DELETE"):
        pre = client.options("/api/sales", headers={"Origin": EVIL, "Access-Control-Request-Method": method})
        assert pre.headers.get("access-control-allow-origin") not in (EVIL, "*"), method
    r = client.get("/api/system/info", headers={**admin, "Origin": EVIL})
    assert r.headers.get("access-control-allow-origin") not in (EVIL, "*")
    assert "access-control-allow-credentials" not in {k.lower() for k in r.headers}


@pytest.mark.parametrize("path,method", [("/api/nope", "GET"), ("/api/sales", "PATCH"), ("/api/sales/not-a-number", "GET")])
def test_error_bodies_are_short_json_without_internals(seeded, path, method):
    client, admin = seeded
    r = client.request(method, path, headers=admin)
    assert r.status_code in (404, 405, 422)
    assert r.headers["content-type"].startswith("application/json")
    assert not re.search(r"Traceback|File \"|\.py\"|sqlalchemy|sqlite3|C:\\\\|/home/", r.text, re.I), r.text[:200]


def test_login_does_not_reveal_which_part_was_wrong(seeded):
    client, _ = seeded
    uid = client.get("/api/auth/users").json()[0]["id"]
    wrong_pin = client.post("/api/auth/login", json={"user_id": uid, "pin": "9999"})
    ghost = client.post("/api/auth/login", json={"user_id": 999999, "pin": "9999"})
    assert wrong_pin.status_code == ghost.status_code == 401
    assert wrong_pin.json()["detail"] == ghost.json()["detail"], "a missing user must look the same as a wrong PIN"
