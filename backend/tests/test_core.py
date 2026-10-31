from app.services.stock import weighted_avg_cost
from tests.conftest import login


def test_weighted_avg_cost():
    assert weighted_avg_cost(0, 100, 10, 50) == 50
    assert weighted_avg_cost(-5, 100, 10, 50) == 50
    assert weighted_avg_cost(10, 100, 10, 50) == 75


def test_setup_and_login(seeded):
    client, admin = seeded
    assert client.get("/api/setup/status").json()["needs_setup"] is False
    assert client.get("/api/auth/me", headers=admin).json()["role"] == "admin"
    assert client.post("/api/setup", json={"business_name": "x", "admin_name": "y", "admin_pin": "1234"}).status_code == 400


def test_wrong_pin_and_roles(seeded):
    client, _ = seeded
    users = client.get("/api/auth/users").json()
    uid = next(u["id"] for u in users if u["name"] == "Caja Demo")
    assert client.post("/api/auth/login", json={"user_id": uid, "pin": "9999"}).status_code == 401
    cajero = login(client, "Caja Demo", "1111")
    assert client.get("/api/users", headers=cajero).status_code == 403
    assert client.get("/api/auth/me").status_code == 401


def test_login_throttle_locks_after_repeated_failures(seeded):
    client, _ = seeded
    users = client.get("/api/auth/users").json()
    uid = next(u["id"] for u in users if u["name"] == "Caja Demo")
    for _ in range(5):
        assert client.post("/api/auth/login", json={"user_id": uid, "pin": "9999"}).status_code == 401
    r = client.post("/api/auth/login", json={"user_id": uid, "pin": "1111"})
    assert r.status_code == 429 and "intentos" in r.json()["detail"]


def test_pin_change_revokes_sessions(seeded):
    client, admin = seeded
    cajero = login(client, "Caja Demo", "1111")
    uid = client.get("/api/auth/me", headers=cajero).json()["id"]
    assert client.patch(f"/api/users/{uid}", json={"pin": "4321"}, headers=admin).status_code == 200
    assert client.get("/api/auth/me", headers=cajero).status_code == 401


def test_health_identifies_app_and_security_headers(client):
    r = client.get("/api/health")
    assert r.json()["app"] == "bloom-cafe"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "no-store"
