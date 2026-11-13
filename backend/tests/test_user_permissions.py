"""Per-user permission exceptions on top of the role (services/roles.py::permissions_of)."""

import pytest

from app.models import AuditLog
from app.permissions import REQUIRES, drop_unsatisfied
from tests.conftest import login


@pytest.fixture()
def api(seeded):
    return seeded


def _id(client, admin, name: str) -> int:
    return next(u["id"] for u in client.get("/api/users", headers=admin).json() if u["name"] == name)


def _put(client, h, uid: int, grants=None, revokes=None):
    return client.put(f"/api/users/{uid}/permissions", json={"grants": grants or [], "revokes": revokes or []}, headers=h)


def _me(client, h) -> set[str]:
    return set(client.get("/api/auth/me", headers=h).json()["permissions"])


def test_drop_unsatisfied_cascades():
    assert drop_unsatisfied({"pos.discount", "sales.void", "stock.adjust"}) == frozenset()
    assert drop_unsatisfied({"pos.sell", "pos.discount"}) == {"pos.sell", "pos.discount"}
    assert all(REQUIRES[k] for k in REQUIRES)


def test_grant_adds_permission_and_requirements(api):
    client, admin = api
    caja = login(client, "Caja Demo", "1111")
    assert "pos.discount" not in _me(client, caja)
    r = _put(client, admin, _id(client, admin, "Caja Demo"), grants=["pos.discount", "customers.manage"])
    assert r.status_code == 200, r.text
    assert {"pos.discount", "customers.manage", "customers.edit"} <= _me(client, caja)


def test_revoke_removes_permission_and_dependents(api):
    client, admin = api
    enc = login(client, "Encargado Demo", "3333")
    assert {"pos.sell", "pos.discount", "sales.void"} <= _me(client, enc)
    assert _put(client, admin, _id(client, admin, "Encargado Demo"), revokes=["pos.sell"]).status_code == 200
    mine = _me(client, enc)
    assert not mine & {"pos.sell", "pos.discount", "sales.void", "pos.courtesy"}
    assert client.get("/api/sales", headers=enc).status_code == 403
    assert "catalog.edit" in mine  # untouched


def test_redundant_entries_are_discarded(api):
    client, admin = api
    r = _put(client, admin, _id(client, admin, "Caja Demo"), grants=["pos.sell"], revokes=["catalog.edit"])
    assert r.status_code == 200
    assert r.json()["perm_grants"] == [] and r.json()["perm_revokes"] == []


def test_validation(api):
    client, admin = api
    uid = _id(client, admin, "Caja Demo")
    assert _put(client, admin, uid, grants=["nope.nope"]).status_code == 400
    assert _put(client, admin, uid, grants=["pos.discount"], revokes=["pos.discount"]).status_code == 400
    assert _put(client, admin, _id(client, admin, "Admin"), grants=["pos.discount"]).status_code == 400
    assert _put(client, admin, 999999, grants=["pos.discount"]).status_code == 404


def test_listing_exposes_overrides_and_effective(api):
    client, admin = api
    uid = _id(client, admin, "Caja Demo")
    _put(client, admin, uid, grants=["pos.discount"], revokes=["customers.edit"])
    row = next(u for u in client.get("/api/users", headers=admin).json() if u["id"] == uid)
    assert row["perm_grants"] == ["pos.discount"] and row["perm_revokes"] == ["customers.edit"]
    assert "pos.discount" in row["effective_permissions"] and "customers.edit" not in row["effective_permissions"]


def test_non_admin_cannot_escalate(api):
    client, admin = api
    # Give the manager the users.manage permission through an exception.
    enc_id = _id(client, admin, "Encargado Demo")
    assert _put(client, admin, enc_id, grants=["users.manage"]).status_code == 200
    enc = login(client, "Encargado Demo", "3333")
    caja_id = _id(client, admin, "Caja Demo")
    assert _put(client, enc, caja_id, grants=["settings.manage"]).status_code == 403  # he doesn't have it
    assert _put(client, enc, caja_id, grants=["pos.discount"]).status_code == 200  # he does
    assert _put(client, enc, _id(client, admin, "Admin"), revokes=["pos.sell"]).status_code in (400, 403)
    # An unrelated user without users.manage can't use the endpoint at all.
    caja = login(client, "Caja Demo", "1111")
    assert _put(client, caja, caja_id, grants=["pos.discount"]).status_code == 403


def test_audit_trail(api, db):
    client, admin = api
    _put(client, admin, _id(client, admin, "Caja Demo"), grants=["pos.discount"])
    db.expire_all()
    row = db.query(AuditLog).filter(AuditLog.action == "update_permissions").one()
    assert row.entity == "user" and row.payload["after"]["grants"] == ["pos.discount"]
    assert row.payload["before"]["grants"] == []


def test_role_change_cleans_redundant_exceptions(api):
    client, admin = api
    uid = _id(client, admin, "Caja Demo")
    _put(client, admin, uid, grants=["stock.view", "pos.discount"], revokes=["customers.edit"])
    r = client.patch(f"/api/users/{uid}", json={"role": "barista"}, headers=admin)
    assert r.status_code == 200, r.text
    # barista already has stock.view (grant redundant); customers.edit isn't in barista (revoke redundant).
    assert r.json()["perm_grants"] == ["pos.discount"] and r.json()["perm_revokes"] == []


def test_roles_list_counts_users_with_exceptions(api):
    client, admin = api
    _put(client, admin, _id(client, admin, "Caja Demo"), grants=["pos.discount"])
    cajero = next(r for r in client.get("/api/roles", headers=admin).json() if r["key"] == "cajero")
    assert cajero["users_with_overrides"] == 1 and cajero["users"] >= 1
