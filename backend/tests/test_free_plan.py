"""Free plan "option C": only N items of each kind stay active for use; the rest is locked, visible
and keeps its history (services/free_plan.py)."""

from datetime import timedelta

import pytest

from app import remote_config
from app.licensing import status
from app.models import Setting, utcnow
from app.services import free_plan
from tests.conftest import login, pro_token

LIMITS = {"products": 5, "customers": 1, "stock_items": 2, "users": 1}


@pytest.fixture()
def free(seeded, monkeypatch):
    """Demo data (more than every cap) on the free plan."""
    client, h = seeded
    monkeypatch.setattr(remote_config, "free_limits", lambda: dict(LIMITS))
    status.store_token(None)
    free_plan.invalidate()
    yield client, h
    status.store_token(pro_token())


def _open_cash(client, h):
    client.post("/api/cash/open", json={"opening_cents": 0}, headers=h)


def _sale(client, h, product_id, **extra):
    _open_cash(client, h)
    body = {"items": [{"product_id": product_id, "qty": 1}], "payments": [], **extra}
    lines = client.get("/api/products", headers=h).json()
    price = next(p for p in lines if p["id"] == product_id)
    body["payments"] = [{"method": "efectivo", "amount_cents": price["price_cents"]}] if price["price_cents"] else []
    return client.post("/api/sales", json=body, headers=h)


def _all_products(client, h):
    return client.get("/api/products", headers=h).json()


def _overview(client, h):
    return client.get("/api/license/free-plan", headers=h).json()


def test_default_active_set_is_the_oldest_by_id_and_deterministic(free):
    client, h = free
    products = sorted(p["id"] for p in _all_products(client, h))
    assert len(products) > 5
    kinds = _overview(client, h)["kinds"]
    assert kinds["products"]["active_ids"] == products[:5]
    assert kinds["products"]["locked"] == len(products) - 5 and kinds["products"]["free_slots"] == 0
    free_plan.invalidate()  # "restart": same answer
    assert _overview(client, h)["kinds"]["products"]["active_ids"] == products[:5]
    locked = {p["id"] for p in _all_products(client, h) if p["locked"]}
    assert locked == set(products[5:])  # everything stays visible, with a lock


def test_pos_catalog_and_sales_only_use_active_products(free, db):
    client, h = free
    ids = sorted(p["id"] for p in _all_products(client, h))
    pos = {p["id"] for p in client.get("/api/pos/catalog", headers=h).json()["products"]}
    assert pos <= set(ids[:5]) and not pos & set(ids[5:])
    locked_product = ids[-1]
    r = _sale(client, h, locked_product)
    assert r.status_code == 402 and "bloqueado" in r.json()["detail"]
    sellable = sorted(pos)[0]
    assert _sale(client, h, sellable).status_code == 200


def test_orders_and_table_lines_use_the_same_rule(free, db):
    """Every order line (POS, table tab, customer orders) goes through sales.LineContext."""
    from fastapi import HTTPException

    from app.schemas.sales import SaleItemIn
    from app.services.sales import LineContext

    client, h = free
    ids = sorted(p["id"] for p in _all_products(client, h))
    with pytest.raises(HTTPException) as exc:
        LineContext(db, [SaleItemIn(product_id=ids[-1])])
    assert exc.value.status_code == 402


def test_locked_product_can_only_be_archived(free):
    client, h = free
    ids = sorted(p["id"] for p in _all_products(client, h))
    locked_id = ids[-1]
    r = client.patch(f"/api/products/{locked_id}", json={"price_cents": 999}, headers=h)
    assert r.status_code == 402
    assert client.delete(f"/api/products/{locked_id}", headers=h).status_code == 200


def test_archiving_frees_a_slot_but_nothing_unlocks_by_itself(free):
    client, h = free
    ids = sorted(p["id"] for p in _all_products(client, h))
    assert client.delete(f"/api/products/{ids[0]}", headers=h).status_code == 200
    kinds = _overview(client, h)["kinds"]["products"]
    assert kinds["active_ids"] == ids[1:5] and kinds["free_slots"] == 1  # ids[5] stays locked
    free_plan.invalidate()
    assert _overview(client, h)["kinds"]["products"]["active_ids"] == ids[1:5]
    # The owner fills the slot: creating one (no cooldown)…
    r = client.post("/api/products", json={"name": "Nuevo", "price_cents": 1000}, headers=h)
    assert r.status_code == 200 and r.json()["locked"] is False
    new_id = r.json()["id"]
    assert client.post("/api/products", json={"name": "Otro", "price_cents": 1000}, headers=h).status_code == 402
    # …or, after archiving another, unlocking a locked one of their choice (no cooldown either).
    client.delete(f"/api/products/{new_id}", headers=h)
    r = client.put("/api/license/free-plan/products", json={"ids": [*ids[1:5], ids[-1]]}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"]["next_swap_at"] is None
    assert _overview(client, h)["kinds"]["products"]["active_ids"] == sorted([*ids[1:5], ids[-1]])


def test_swapping_has_a_cooldown(free, db):
    client, h = free
    ids = sorted(p["id"] for p in _all_products(client, h))
    swap1 = [*ids[:4], ids[5]]
    r = client.put("/api/license/free-plan/products", json={"ids": swap1}, headers=h)
    assert r.status_code == 200 and r.json()["status"]["next_swap_at"]
    r = client.put("/api/license/free-plan/products", json={"ids": [*ids[:4], ids[6]]}, headers=h)
    assert r.status_code == 409 and "7 días" in r.json()["detail"]
    # Adding into a free slot is still allowed during the cooldown
    client.delete(f"/api/products/{ids[0]}", headers=h)
    r = client.put("/api/license/free-plan/products", json={"ids": [*ids[1:4], ids[5], ids[6]]}, headers=h)
    assert r.status_code == 200, r.text
    # After the cooldown, swapping works again
    row = db.get(Setting, "free_actives")
    db.refresh(row)
    value = dict(row.value)
    value["products"] = {**value["products"], "swapped_at": (utcnow() - timedelta(days=8)).isoformat()}
    row.value = value
    db.commit()
    free_plan.invalidate()
    r = client.put("/api/license/free-plan/products", json={"ids": [*ids[1:4], ids[5], ids[7]]}, headers=h)
    assert r.status_code == 200, r.text
    assert len(r.json()["status"]["active_ids"]) == 5


def test_cooldown_comes_from_the_remote_config(free, monkeypatch):
    client, h = free
    monkeypatch.setattr(remote_config, "free_limits", lambda: {**LIMITS, "swap_cooldown_days": 0})
    ids = sorted(p["id"] for p in _all_products(client, h))
    for other in (ids[5], ids[6]):
        r = client.put("/api/license/free-plan/products", json={"ids": [*ids[:4], other]}, headers=h)
        assert r.status_code == 200, r.text
    assert client.put("/api/license/free-plan/products", json={"ids": ids[:6]}, headers=h).status_code == 400


def test_locked_customer_cant_buy_but_its_balance_can_be_collected(free, db):
    from app.models import Customer

    client, h = free
    customers = sorted(c["id"] for c in client.get("/api/customers", headers=h).json())
    assert len(customers) >= 2
    active, locked = customers[0], customers[1]
    c = db.get(Customer, locked)
    c.balance_cents = 50_000
    db.commit()
    rows = {c["id"]: c for c in client.get("/api/customers", headers=h).json()}
    assert rows[locked]["locked"] and not rows[active]["locked"]
    assert client.get(f"/api/customers/{locked}", headers=h).json()["locked"] is True
    pid = client.get("/api/pos/catalog", headers=h).json()["products"][0]["id"]
    r = _sale(client, h, pid, customer_id=locked)
    assert r.status_code == 402 and "cliente" in r.json()["detail"].lower()
    assert _sale(client, h, pid, customer_id=active).status_code == 200
    assert client.patch(f"/api/customers/{locked}", json={"notes": "x"}, headers=h).status_code == 402
    assert client.post(f"/api/customers/{locked}/points", json={"points": 5, "reason": "x"}, headers=h).status_code == 402
    r = client.post(f"/api/customers/{locked}/payments", json={"amount_cents": 20_000, "method": "efectivo"}, headers=h)
    assert r.status_code == 200, r.text
    assert client.get(f"/api/customers/{locked}", headers=h).json()["balance_cents"] == 30_000


def test_locked_stock_items_cant_be_used_in_recipes_or_movements(free):
    client, h = free
    items = sorted(i["id"] for i in client.get("/api/stock/items", headers=h).json())
    ok, locked = items[0], items[-1]
    rows = {i["id"]: i for i in client.get("/api/stock/items", headers=h).json()}
    assert rows[locked]["locked"] and not rows[ok]["locked"]
    assert client.post("/api/stock/adjust", json={"stock_item_id": locked, "delta": 5, "reason": "x"}, headers=h).status_code == 402
    assert client.post("/api/stock/waste", json={"stock_item_id": locked, "qty": 1, "reason": "x"}, headers=h).status_code == 402
    assert client.post("/api/stock/adjust", json={"stock_item_id": ok, "delta": 5, "reason": "x"}, headers=h).status_code == 200
    assert client.patch(f"/api/stock/items/{locked}", json={"min_qty": 3}, headers=h).status_code == 402
    # Recipes: a locked stock item can't be added (viewing is fine)
    pid = client.get("/api/pos/catalog", headers=h).json()["products"][0]["id"]
    product = client.get(f"/api/products/{pid}", headers=h).json()
    recipe = [{"stock_item_id": r["stock_item_id"], "qty": r["qty"]} for r in product["recipe_items"]]
    r = client.patch(f"/api/products/{pid}", json={"recipe_items": [*recipe, {"stock_item_id": locked, "qty": 1}]}, headers=h)
    assert r.status_code == 402
    # Re-saving the existing recipe (even if it used a now-locked item) still works
    assert client.patch(f"/api/products/{pid}", json={"recipe_items": recipe}, headers=h).status_code == 200
    count = client.post("/api/stock/counts", json={}, headers=h).json()
    assert {i["stock_item_id"] for i in count["items"]} <= set(items[:2])


def test_only_active_users_can_log_in_and_admin_is_always_one(free, monkeypatch):
    client, h = free
    users = client.get("/api/auth/users").json()
    assert any(u["locked"] for u in users)
    admin = next(u for u in users if u["name"] == "Admin")
    assert not admin["locked"]
    caja = next(u for u in users if u["name"] == "Caja Demo")
    r = client.post("/api/auth/login", json={"user_id": caja["id"], "pin": "1111"})
    assert r.status_code == 402 and "bloqueado" in r.json()["detail"]
    assert client.put("/api/license/free-plan/users", json={"ids": [caja["id"]]}, headers=h).status_code == 400
    monkeypatch.setattr(remote_config, "free_limits", lambda: {**LIMITS, "users": 2})
    r = client.put("/api/license/free-plan/users", json={"ids": [admin["id"], caja["id"]]}, headers=h)
    assert r.status_code == 200, r.text
    login(client, "Caja Demo", "1111")


def test_going_back_to_pro_unlocks_everything_and_keeps_the_selection(free, db):
    client, h = free
    ids = sorted(p["id"] for p in _all_products(client, h))
    client.put("/api/license/free-plan/products", json={"ids": [*ids[:4], ids[-1]]}, headers=h)
    status.store_token(pro_token())
    assert not any(p["locked"] for p in _all_products(client, h))
    pos = {p["id"] for p in client.get("/api/pos/catalog", headers=h).json()["products"]}
    assert set(ids[5:-1]) & pos
    assert _sale(client, h, ids[5]).status_code == 200
    login(client, "Caja Demo", "1111")
    # Free again: the owner's selection is still there
    status.store_token(None)
    assert _overview(client, h)["kinds"]["products"]["active_ids"] == sorted([*ids[:4], ids[-1]])


def test_free_actives_setting_is_not_writable_through_the_generic_endpoint(free):
    client, h = free
    assert client.put("/api/settings/free_actives", json={"products": {"ids": [1, 2, 3, 4, 5, 6, 7]}}, headers=h).status_code == 404
