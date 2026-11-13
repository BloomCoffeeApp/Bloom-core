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
    assert _perms(client, dep) == {"stock.view", "stock.receive"}
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
