"""Idempotency of expenses (create / pay) and stock (adjust, waste, count create / apply): the same request sent twice
with one `Idempotency-Key` is done once, and a key reused for another request is refused."""
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Expense, InventoryCount, StockMovement

K = "k-" + "e" * 30


def _count(model) -> int:
    with SessionLocal() as s:
        return s.scalar(select(func.count()).select_from(model))


def _category(client, h) -> int:
    return client.get("/api/expenses/categories", headers=h).json()[0]["id"]


def _expense(cat, **kw):
    return {"category_id": cat, "description": "Luz", "amount_cents": 150000, "status": "paid", **kw}


def test_an_expense_sent_twice_is_loaded_once(seeded):
    client, admin = seeded
    body = _expense(_category(client, admin))
    before = _count(Expense)
    a = client.post("/api/expenses", json=body, headers={**admin, "Idempotency-Key": K})
    b = client.post("/api/expenses", json=body, headers={**admin, "Idempotency-Key": K})
    assert a.status_code == b.status_code == 200
    assert a.json()["id"] == b.json()["id"] and b.headers["idempotent-replay"] == "true"
    assert _count(Expense) == before + 1
    # The same key for another expense is refused, not merged.
    other = client.post("/api/expenses", json=_expense(body["category_id"], amount_cents=1), headers={**admin, "Idempotency-Key": K})
    assert other.status_code == 409
    # Without a key nothing changes: two identical expenses are two expenses.
    assert client.post("/api/expenses", json=body, headers=admin).status_code == 200
    assert client.post("/api/expenses", json=body, headers=admin).status_code == 200
    assert _count(Expense) == before + 3


def test_paying_an_expense_twice_with_one_key_is_not_an_error(seeded):
    client, admin = seeded
    pending = client.post("/api/expenses", json=_expense(_category(client, admin), status="pending"), headers=admin).json()
    pay = {"payment_method": "efectivo", "from_cash": False}
    a = client.post(f"/api/expenses/{pending['id']}/pay", json=pay, headers={**admin, "Idempotency-Key": K})
    b = client.post(f"/api/expenses/{pending['id']}/pay", json=pay, headers={**admin, "Idempotency-Key": K})
    assert a.status_code == b.status_code == 200, b.text
    assert b.headers["idempotent-replay"] == "true" and b.json()["status"] == "paid"
    # Without the key the second tap is the old 409 ("ya está pagado").
    assert client.post(f"/api/expenses/{pending['id']}/pay", json=pay, headers=admin).status_code == 409


def _item(client, h, name="Leche entera"):
    return next(i for i in client.get("/api/stock/items", headers=h).json() if i["name"] == name)


def test_a_stock_adjustment_sent_twice_moves_stock_once(seeded):
    client, admin = seeded
    item = _item(client, admin)
    body = {"stock_item_id": item["id"], "delta": 500, "reason": "Conteo rápido"}
    before = _count(StockMovement)
    a = client.post("/api/stock/adjust", json=body, headers={**admin, "Idempotency-Key": K})
    b = client.post("/api/stock/adjust", json=body, headers={**admin, "Idempotency-Key": K})
    assert a.status_code == b.status_code == 200
    assert b.headers["idempotent-replay"] == "true"
    assert _count(StockMovement) == before + 1
    assert _item(client, admin)["current_qty"] == round(item["current_qty"] + 500, 4)
    assert client.post("/api/stock/adjust", json={**body, "delta": 1}, headers={**admin, "Idempotency-Key": K}).status_code == 409


def test_a_waste_sent_twice_discards_once(seeded):
    client, admin = seeded
    item = _item(client, admin)
    body = {"stock_item_id": item["id"], "qty": 100, "reason_code": "expired"}
    a = client.post("/api/stock/waste", json=body, headers={**admin, "Idempotency-Key": K})
    b = client.post("/api/stock/waste", json=body, headers={**admin, "Idempotency-Key": K})
    assert a.status_code == b.status_code == 200, a.text
    assert b.headers["idempotent-replay"] == "true"
    assert _item(client, admin)["current_qty"] == round(item["current_qty"] - 100, 4)


def test_a_count_is_created_and_applied_once(seeded):
    client, admin = seeded
    before = _count(InventoryCount)
    a = client.post("/api/stock/counts", json={"category_id": None}, headers={**admin, "Idempotency-Key": K})
    b = client.post("/api/stock/counts", json={"category_id": None}, headers={**admin, "Idempotency-Key": K})
    assert a.status_code == b.status_code == 200
    assert a.json()["id"] == b.json()["id"] and b.headers["idempotent-replay"] == "true"
    assert _count(InventoryCount) == before + 1
    count = a.json()
    first = count["items"][0]
    client.patch(f"/api/stock/counts/{count['id']}/items/{first['id']}", json={"counted_qty": first["expected_qty"] + 7}, headers=admin)
    k2 = "k-" + "f" * 30
    x = client.post(f"/api/stock/counts/{count['id']}/apply", headers={**admin, "Idempotency-Key": k2})
    y = client.post(f"/api/stock/counts/{count['id']}/apply", headers={**admin, "Idempotency-Key": k2})
    assert x.status_code == y.status_code == 200, y.text
    assert y.headers["idempotent-replay"] == "true" and y.json()["status"] == "applied"
