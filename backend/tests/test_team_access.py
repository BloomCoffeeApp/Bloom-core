"""Staff phone app access: the team code behind the register's QR, the staff-only login and open sessions."""

from datetime import date, timedelta

from app.models import utcnow

import pytest

from tests.conftest import login


@pytest.fixture()
def api(seeded):
    return seeded


def _key() -> str:
    from app.db import SessionLocal
    from app.services import team_access

    with SessionLocal() as db:
        return team_access.config(db)["key"]


def _user(client, admin, name, role, pin="4321"):
    r = client.post("/api/users", json={"name": name, "pin": pin, "role": role, "color": "sky"}, headers=admin)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _login_equipo(client, uid, key, pin="4321"):
    return client.post("/api/auth/login", json={"user_id": uid, "pin": pin, "client": "equipo", "team_key": key})


def test_users_list_needs_the_team_code(api):
    client, _admin = api
    key = _key()
    assert client.get("/api/team/users").status_code == 403
    assert client.get("/api/team/users", params={"k": "nope"}).status_code == 403
    assert client.get("/api/team/users", params={"k": key}).status_code == 200
    assert client.get("/api/team/status", params={"k": key}).json() == {"ok": True}


def test_users_list_only_has_people_with_team_permissions(api):
    client, admin = api
    _user(client, admin, "Mozo A", "mozo")
    _user(client, admin, "Cocina A", "cocina")
    _user(client, admin, "Depo A", "deposito")
    role = client.post("/api/roles", json={"name": "Solo reportes", "permissions": ["reports.view"]}, headers=admin)
    assert role.status_code == 200, role.text
    _user(client, admin, "Reportes Z", role.json()["key"])
    names = {u["name"] for u in client.get("/api/team/users", params={"k": _key()}).json()}
    assert {"Mozo A", "Cocina A", "Depo A"} <= names
    assert "Reportes Z" not in names
    # A per-person exception is enough to appear.
    uid = _user(client, admin, "Reportes Y", role.json()["key"])
    client.put(f"/api/users/{uid}/permissions", json={"grants": ["tables.serve"], "revokes": []}, headers=admin)
    names = {u["name"] for u in client.get("/api/team/users", params={"k": _key()}).json()}
    assert "Reportes Y" in names


def test_equipo_login_requires_a_valid_code_and_a_team_permission(api):
    client, admin = api
    uid = _user(client, admin, "Mozo B", "mozo")
    role = client.post("/api/roles", json={"name": "Solo reportes", "permissions": ["reports.view"]}, headers=admin)
    bar = _user(client, admin, "Reportes W", role.json()["key"], pin="5555")
    key = _key()
    assert _login_equipo(client, uid, None).status_code == 403
    assert _login_equipo(client, uid, "wrong").status_code == 403
    r = _login_equipo(client, uid, key)
    assert r.status_code == 200, r.text
    # Right code but nothing to do in the team app: refused, not logged in.
    assert _login_equipo(client, bar, key, pin="5555").status_code == 403
    # The normal login still works without a code.
    assert client.post("/api/auth/login", json={"user_id": uid, "pin": "4321"}).status_code == 200


def test_wrong_codes_are_throttled(api):
    client, _admin = api
    for _ in range(5):
        assert client.get("/api/team/users", params={"k": "x"}).status_code == 403
    assert client.get("/api/team/users", params={"k": _key()}).status_code == 429


def test_code_rotates_daily_and_by_hand(api):
    from app.db import SessionLocal
    from app.services import settings as settings_svc
    from app.services import team_access

    client, admin = api
    first = _key()
    with SessionLocal() as db:  # pretend the code was made two days ago
        cfg = settings_svc.get(db, team_access.SETTING)
        settings_svc.put(db, team_access.SETTING, {**cfg, "rotated_on": (date.today() - timedelta(days=2)).isoformat()})
        db.commit()
    assert _key() != first
    # Manual mode keeps the code across days.
    assert client.put("/api/team/config", json={"rotate": "manual"}, headers=admin).status_code == 200
    stable = _key()
    with SessionLocal() as db:
        cfg = settings_svc.get(db, team_access.SETTING)
        settings_svc.put(db, team_access.SETTING, {**cfg, "rotated_on": "2000-01-01"})
        db.commit()
    assert _key() == stable
    assert client.post("/api/team/rotate", headers=admin).status_code == 200
    assert _key() != stable


def test_the_code_never_travels_in_the_generic_settings(api):
    client, admin = api
    key = _key()
    body = client.get("/api/settings", headers=admin).text
    assert key not in body and "team_access" not in body
    assert client.put("/api/settings/team_access", json={"key": "x"}, headers=admin).status_code == 404


def test_config_validation_and_permissions(api):
    client, admin = api
    assert client.put("/api/team/config", json={"rotate": "weekly"}, headers=admin).status_code == 422
    assert client.put("/api/team/config", json={"lock_minutes": 0}, headers=admin).status_code == 422
    assert client.put("/api/team/config", json={"lock_minutes": 45}, headers=admin).json()["lock_minutes"] == 45
    assert client.get("/api/team/info", headers=admin).json()["code"] == _key()
    _user(client, admin, "Mozo C", "mozo")
    h = login(client, "Mozo C", "4321")
    assert client.post("/api/team/rotate", headers=h).status_code == 403
    assert client.put("/api/team/config", json={"lock_minutes": 5}, headers=h).status_code == 403
    assert client.get("/api/team/lock", headers=h).json() == {"lock_minutes": 45}
    assert client.get("/api/team/qr", headers=h).status_code in (200, 404)  # 404 = no LAN in the test box


def test_sessions_list_marks_the_client_and_can_be_disconnected(api):
    client, admin = api
    uid = _user(client, admin, "Mozo D", "mozo")
    token = _login_equipo(client, uid, _key()).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    login(client, "Mozo D", "4321")  # a second session from the normal app
    rows = client.get(f"/api/users/{uid}/sessions", headers=admin).json()
    assert {r["client"] for r in rows} == {"equipo", None}
    mine = client.get("/api/auth/sessions", headers=h).json()
    assert [r["client"] for r in mine if r["current"]] == ["equipo"]
    equipo = next(r for r in rows if r["client"] == "equipo")
    assert client.delete(f"/api/users/{uid}/sessions/{equipo['id']}", headers=admin).status_code == 200
    assert client.get("/api/auth/me", headers=h).status_code == 401  # that phone is out
    assert [r["client"] for r in client.get(f"/api/users/{uid}/sessions", headers=admin).json()] == [None]


def test_close_other_sessions_keeps_the_current_one(api):
    client, admin = api
    _user(client, admin, "Mozo E", "mozo")
    a = login(client, "Mozo E", "4321")
    b = login(client, "Mozo E", "4321")
    assert client.post("/api/auth/sessions/close-others", headers=a).json() == {"closed": 1}
    assert client.get("/api/auth/me", headers=a).status_code == 200
    assert client.get("/api/auth/me", headers=b).status_code == 401


def test_nobody_disconnects_an_admin_or_someone_above_them(api):
    client, admin = api
    admin_id = next(u["id"] for u in client.get("/api/users", headers=admin).json() if u["name"] == "Admin")
    _user(client, admin, "Encargado F", "encargado")
    eh = login(client, "Encargado F", "4321")
    sid = client.get(f"/api/users/{admin_id}/sessions", headers=admin).json()[0]["id"]
    assert client.get(f"/api/users/{admin_id}/sessions", headers=eh).status_code == 403
    assert client.delete(f"/api/users/{admin_id}/sessions/{sid}", headers=eh).status_code == 403
    assert client.delete(f"/api/users/{admin_id}/sessions/999999", headers=admin).status_code == 404


def test_last_seen_is_touched_at_most_once_a_minute(api):
    from app.db import SessionLocal
    from app.models import UserSession

    client, admin = api
    client.get("/api/auth/me", headers=admin)
    with SessionLocal() as db:
        s = db.query(UserSession).order_by(UserSession.id.desc()).first()
        assert s.last_seen_at is not None
        s.last_seen_at = utcnow() - timedelta(minutes=5)
        db.commit()
    client.get("/api/auth/me", headers=admin)
    with SessionLocal() as db:
        s = db.query(UserSession).order_by(UserSession.id.desc()).first()
        assert s.last_seen_at > utcnow() - timedelta(minutes=1)
