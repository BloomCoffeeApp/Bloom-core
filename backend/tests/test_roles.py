"""Editable roles and permissions (app/permissions.py, services/roles.py)."""

import pytest

from app.models import AuditLog
from app.permissions import ALL, BUILTIN_ROLES, PERMISSIONS
from tests.conftest import login


@pytest.fixture()
def api(seeded):
    return seeded


def _user(client, h, name: str, role: str, pin: str = "4321") -> dict[str, str]:
    r = client.post("/api/users", json={"name": name, "pin": pin, "role": role, "color": "sky"}, headers=h)
    assert r.status_code == 200, r.text
    return login(client, name, pin)


def test_builtin_roles_keep_their_historical_permissions():
    # tables.serve / kitchen.use are the old "any logged user may move orders" made explicit.
    sell = {"pos.sell", "pos.courtesy", "cash.open_close", "cash.movements", "customers.edit",
            "tables.serve", "kitchen.use"}
    assert BUILTIN_ROLES["admin"]["permissions"] == ALL
    assert BUILTIN_ROLES["cajero"]["permissions"] == sell
    assert BUILTIN_ROLES["barista"]["permissions"] == {"barista.use", "stock.view", "kitchen.use"}
    assert BUILTIN_ROLES["mozo"]["permissions"] == {"tables.serve"}
    assert BUILTIN_ROLES["cocina"]["permissions"] == {"kitchen.use"}
    assert BUILTIN_ROLES["deposito"]["permissions"] == {"stock.view", "stock.receive"}
    enc = BUILTIN_ROLES["encargado"]["permissions"]
    assert sell <= enc and {"pos.discount", "sales.void", "catalog.edit", "reports.view", "stock.adjust"} <= enc
    # Admin-level things stay out of the manager's default set.
    assert not enc & {"settings.manage", "users.manage", "system.manage", "staff.manage"}


# (method, path, body, {role: allowed}) — the same answers the old fixed role checks gave.
MATRIX = [
    ("GET", "/api/sales", None, {"cajero": True, "barista": False, "encargado": True}),
    ("GET", "/api/cash/sessions", None, {"cajero": True, "barista": False, "encargado": True}),
    ("GET", "/api/stock/items", None, {"cajero": False, "barista": True, "encargado": True}),
    ("POST", "/api/stock/adjust", {"stock_item_id": 999999, "new_qty": 1, "reason": "x"}, {"cajero": False, "barista": False, "encargado": True}),
    ("POST", "/api/products", {}, {"cajero": False, "barista": False, "encargado": True}),
    ("GET", "/api/customers", None, {"cajero": True, "barista": False, "encargado": True}),
    ("DELETE", "/api/customers/999999", None, {"cajero": False, "barista": False, "encargado": True}),
    ("POST", "/api/notices", {}, {"cajero": False, "barista": False, "encargado": True}),
    ("PUT", "/api/orders/settings", {}, {"cajero": False, "barista": False, "encargado": True}),
    ("GET", "/api/users", None, {"cajero": False, "barista": False, "encargado": False}),
    ("PUT", "/api/settings/lock_minutes", 10, {"cajero": False, "barista": False, "encargado": False}),
    ("GET", "/api/system/backups", None, {"cajero": False, "barista": False, "encargado": False}),
    ("POST", "/api/roles", {"name": "x"}, {"cajero": False, "barista": False, "encargado": False}),
]
USERS = {"cajero": ("Caja Demo", "1111"), "barista": ("Barista Demo", "2222"), "encargado": ("Encargado Demo", "3333")}


def test_default_mapping_matches_old_role_checks(api):
    client, admin = api
    heads = {role: login(client, *cred) for role, cred in USERS.items()}
    for method, path, body, expect in MATRIX:
        for role, allowed in expect.items():
            r = client.request(method, path, json=body, headers=heads[role])
            assert (r.status_code != 403) == allowed, (method, path, role, r.status_code, r.text)
        assert client.request(method, path, json=body, headers=admin).status_code != 403, (method, path)


def test_me_exposes_permissions_and_role_name(api):
    client, admin = api
    me = client.get("/api/auth/me", headers=login(client, "Caja Demo", "1111")).json()
    assert me["role_name"] == "Cajero" and "pos.sell" in me["permissions"] and "pos.discount" not in me["permissions"]
    assert set(client.get("/api/auth/me", headers=admin).json()["permissions"]) == set(PERMISSIONS)
    users = client.get("/api/auth/users").json()
    assert {u["role_name"] for u in users} >= {"Administrador", "Cajero"}


def test_custom_role_is_enforced(api):
    client, admin = api
    r = client.post("/api/roles", json={"name": "Runner", "permissions": ["pos.sell", "notices.manage"]}, headers=admin)
    assert r.status_code == 200, r.text
    role = r.json()
    assert role["key"] == "runner" and not role["builtin"] and role["permissions"] == ["notices.manage", "pos.sell"]
    mozo = _user(client, admin, "Juan Mozo", "runner")
    me = client.get("/api/auth/me", headers=mozo).json()
    assert me["role"] == "runner" and me["role_name"] == "Runner"
    assert client.get("/api/sales", headers=mozo).status_code == 200
    assert client.post("/api/notices", json={"title": "Hola", "body": ""}, headers=mozo).status_code != 403
    assert client.get("/api/cash/sessions", headers=mozo).status_code == 403  # no cash.open_close
    assert client.get("/api/stock/items", headers=mozo).status_code == 403
    assert client.get("/api/customers", headers=mozo).status_code == 403
    # Editing the role applies on the next request (no re-login).
    client.patch("/api/roles/runner", json={"permissions": ["pos.sell", "customers.manage"]}, headers=admin)
    assert client.get("/api/customers", headers=mozo).status_code == 200  # customers.manage brings customers.edit
    assert client.post("/api/notices", json={"title": "Hola", "body": ""}, headers=mozo).status_code == 403


def test_custom_role_without_discount_cannot_discount(api):
    client, admin = api
    client.post("/api/roles", json={"name": "Caja junior", "permissions": ["pos.sell", "cash.open_close"]}, headers=admin)
    h = _user(client, admin, "Junior", "caja_junior")
    from app.services import roles
    from app.db import SessionLocal
    from app.models import User

    with SessionLocal() as db:
        u = db.query(User).filter_by(name="Junior").one()
        assert roles.has(u, "pos.sell") and not roles.has(u, "pos.discount") and not roles.has(u, "pos.courtesy")
    assert client.get("/api/auth/me", headers=h).json()["permissions"] == ["cash.open_close", "pos.sell"]


def test_editing_and_resetting_a_builtin_role(api):
    client, admin = api
    cajero = login(client, "Caja Demo", "1111")
    assert client.get("/api/customers", headers=cajero).status_code == 200
    r = client.patch("/api/roles/cajero", json={"permissions": ["pos.sell", "cash.open_close", "cash.movements"]}, headers=admin)
    assert r.status_code == 200 and r.json()["customized"]
    assert client.get("/api/customers", headers=cajero).status_code == 403
    r = client.post("/api/roles/cajero/reset", headers=admin)
    assert r.status_code == 200 and not r.json()["customized"]
    assert client.get("/api/customers", headers=cajero).status_code == 200


def test_lockout_protection(api):
    client, admin = api
    assert client.patch("/api/roles/admin", json={"permissions": []}, headers=admin).status_code == 400
    assert client.delete("/api/roles/cajero", headers=admin).status_code == 400
    assert client.post("/api/roles", json={"name": "Cajero"}, headers=admin).status_code == 409  # duplicated name
    assert client.post("/api/roles", json={"name": "X", "permissions": ["nope"]}, headers=admin).status_code == 400
    client.post("/api/roles", json={"name": "Temporal", "permissions": ["pos.sell"]}, headers=admin)
    _user(client, admin, "Temp", "temporal")
    assert client.delete("/api/roles/temporal", headers=admin).status_code == 409  # in use
    # The last admin can't demote itself.
    me = client.get("/api/auth/me", headers=admin).json()
    assert client.patch(f"/api/users/{me['id']}", json={"role": "cajero"}, headers=admin).status_code == 400
    # Unknown role on a user.
    assert client.post("/api/users", json={"name": "Z", "pin": "1234", "role": "inventado"}, headers=admin).status_code == 400


def test_delegated_user_management_cannot_escalate(api):
    client, admin = api
    client.post("/api/roles", json={"name": "Jefe de turno", "permissions": ["users.manage", "pos.sell", "cash.open_close"]},
                headers=admin)
    jefe = _user(client, admin, "Jefa", "jefe_de_turno")
    assert client.get("/api/users", headers=jefe).status_code == 200
    # Can't create admins nor roles with more permissions than their own.
    assert client.post("/api/users", json={"name": "A2", "pin": "1234", "role": "admin"}, headers=jefe).status_code == 403
    assert client.post("/api/users", json={"name": "E2", "pin": "1234", "role": "encargado"}, headers=jefe).status_code == 403
    assert client.post("/api/users", json={"name": "C2", "pin": "1234", "role": "jefe_de_turno"}, headers=jefe).status_code == 200
    # Can't touch an admin, nor the roles editor.
    admin_id = client.get("/api/auth/me", headers=admin).json()["id"]
    assert client.patch(f"/api/users/{admin_id}", json={"pin": "9999"}, headers=jefe).status_code == 403
    assert client.patch("/api/roles/cajero", json={"permissions": []}, headers=jefe).status_code == 403


def test_role_changes_are_audited(api, db):
    client, admin = api
    client.post("/api/roles", json={"name": "Auditado", "permissions": ["pos.sell"]}, headers=admin)
    client.patch("/api/roles/auditado", json={"permissions": ["pos.sell", "sales.void"]}, headers=admin)
    client.delete("/api/roles/auditado", headers=admin)
    db.expire_all()
    rows = db.query(AuditLog).filter(AuditLog.entity == "role").order_by(AuditLog.id).all()
    assert [r.action for r in rows][-3:] == ["create", "update", "delete"]
    assert rows[-2].payload["added"] == ["sales.void"]
