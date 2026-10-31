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


def test_unknown_api_path_is_404_not_the_spa(client):
    """A Pro endpoint missing in the Free edition must not fall through to index.html."""
    r = client.get("/api/no-existe")
    assert r.status_code == 404 and "text/html" not in r.headers.get("content-type", "")


def test_lan_mode_switches_live_and_reports_reachability(seeded, monkeypatch):
    """LAN mode is applied when the setting is saved (no restart) and the UI learns if phones can reach us."""
    from app import lan
    from app.services import system

    client, admin = seeded
    calls: list[bool] = []
    monkeypatch.setattr(lan, "apply", calls.append)
    monkeypatch.setattr(system, "network_category", lambda ip: "Public")
    assert client.put("/api/settings/network", json={"lan_enabled": True}, headers=admin).status_code == 200
    assert calls == [True]
    info = client.get("/api/system/info", headers=admin).json()
    assert info["lan_enabled"] is True and info["lan_active"] is True  # outside the launcher: trusts the setting
    assert info["network_public"] is bool(info["lan_ips"])
    client.put("/api/settings/network", json={"lan_enabled": False}, headers=admin)
    assert calls == [True, False]


def test_lan_listener_is_a_noop_outside_the_launcher():
    from app import lan

    lan.apply(True)  # tests/dev: never opens a network socket
    assert lan._server is None and lan.active(False) is False
