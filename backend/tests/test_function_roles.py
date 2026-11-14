"""Roles by function (mozo, cocina, depósito): what each may do with orders and calls."""

import pytest

from tests.conftest import login


@pytest.fixture()
def api(seeded):
    return seeded


def _user(client, admin, name: str, role: str) -> dict[str, str]:
    r = client.post("/api/users", json={"name": name, "pin": "4321", "role": role, "color": "sky"}, headers=admin)
    assert r.status_code == 200, r.text
    return login(client, name, "4321")


def _perms(client, h) -> set[str]:
    return set(client.get("/api/auth/me", headers=h).json()["permissions"])


def test_function_roles_exist_and_have_their_permissions(api):
    client, admin = api
    mozo, cocina, dep = (_user(client, admin, n, r) for n, r in
                         (("Mozo X", "mozo"), ("Cocina X", "cocina"), ("Deposito X", "deposito")))
    assert _perms(client, mozo) == {"tables.serve"}
    assert _perms(client, cocina) == {"kitchen.use"}
    assert _perms(client, dep) == {"stock.view", "stock.receive", "stock.count"}
    keys = {r["key"] for r in client.get("/api/roles", headers=admin).json()}
    assert {"mozo", "cocina", "deposito"} <= keys


def test_stock_receive_pulls_stock_view(api):
    client, admin = api
    r = client.post("/api/roles", json={"name": "Recibe", "permissions": ["stock.receive"]}, headers=admin)
    assert set(r.json()["permissions"]) == {"stock.receive", "stock.view"}


def test_orders_actions_follow_function_permissions(api):
    client, admin = api
    # The order doesn't exist: what matters is permission (403) versus past the guard (404).
    expected = {"Mozo X": ("mozo", True), "Cocina X": ("cocina", True), "Deposito X": ("deposito", False)}
    for name, (role, allowed) in expected.items():
        h = _user(client, admin, name, role)
        for method, path, body in (("POST", "/api/orders/999999/status", {"status": "ready"}),
                                   ("POST", "/api/waiter-calls/999999/resolve", None)):
            code = client.request(method, path, json=body, headers=h).status_code
            assert (code != 403) == allowed, (name, path, code)
    # Still open to the register and the bar, as before.
    for who in (("Caja Demo", "1111"), ("Barista Demo", "2222")):
        assert client.post("/api/orders/999999/status", json={"status": "ready"},
                           headers=login(client, *who)).status_code != 403


def test_kitchen_moves_orders_forward_but_never_cancels_or_rejects(api):
    client, admin = api
    cocina = _user(client, admin, "Cocina Y", "cocina")
    for status in ("cancelled", "rejected"):
        r = client.post("/api/orders/999999/status", json={"status": status}, headers=cocina)
        assert r.status_code == 403 and "caja" in r.json()["detail"], (status, r.text)
    # Moving forward is still theirs (the order doesn't exist: past the guard, so 404 and not 403).
    assert client.post("/api/orders/999999/status", json={"status": "ready"}, headers=cocina).status_code == 404
    # The register, the floor and the manager still cancel (past the guard).
    for who in (("Caja Demo", "1111"), ("Encargado Demo", "3333")):
        h = login(client, *who)
        assert client.post("/api/orders/999999/status", json={"status": "cancelled"}, headers=h).status_code == 404
    mozo = _user(client, admin, "Mozo Y", "mozo")
    assert client.post("/api/orders/999999/status", json={"status": "cancelled"}, headers=mozo).status_code == 404


def test_kitchen_can_use_the_quick_discard(api):
    client, admin = api
    cocina = _user(client, admin, "Cocina Z", "cocina")
    assert client.get("/api/stock/quick-items", headers=cocina).status_code == 200
    deposito = _user(client, admin, "Deposito Z", "deposito")
    assert client.get("/api/stock/quick-items", headers=deposito).status_code == 403


def test_the_warehouse_counts_but_only_adjusters_apply(api):
    client, admin = api
    dep = _user(client, admin, "Deposito C", "deposito")
    created = client.post("/api/stock/counts", json={"category_id": None, "notes": None}, headers=dep)
    assert created.status_code == 200, created.text
    count = created.json()
    item = count["items"][0]
    r = client.patch(f"/api/stock/counts/{count['id']}/items/{item['id']}", json={"counted_qty": 3}, headers=dep)
    assert r.status_code == 200, r.text
    bulk = client.patch(f"/api/stock/counts/{count['id']}/items", json={"items": [{"id": item["id"], "counted_qty": 4}]}, headers=dep)
    assert bulk.status_code == 200, bulk.text
    assert client.post(f"/api/stock/counts/{count['id']}/apply", headers=dep).status_code == 403
    assert client.post(f"/api/stock/counts/{count['id']}/cancel", headers=dep).status_code == 403
    assert client.post(f"/api/stock/counts/{count['id']}/apply", headers=admin).status_code == 200
    # The cook has no stock permissions at all.
    cocina = _user(client, admin, "Cocina C", "cocina")
    assert client.post("/api/stock/counts", json={"category_id": None, "notes": None}, headers=cocina).status_code == 403


def test_stock_count_pulls_stock_view(api):
    client, admin = api
    r = client.post("/api/roles", json={"name": "Cuenta", "permissions": ["stock.count"]}, headers=admin)
    assert set(r.json()["permissions"]) == {"stock.count", "stock.view"}
