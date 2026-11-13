"""Idempotency: the same money operation sent twice (double click, retry after a timeout, flaky tablet) is done ONCE.

Covers sales, cash movements and customer account payments: sequential repeats, simultaneous repeats, a key reused
for a different request, malformed keys, failures not consuming the key, and the pruning of old keys."""
import threading
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import SessionLocal
from app.main import create_app
from app.models import CashMovement, Customer, CustomerAccountMovement, IdempotencyKey, Product, Sale, StockItem
from app.models.base import utcnow
from tests.conftest import login

KEY = "k-" + "a" * 30


def _latte(db) -> tuple[int, int]:
    p = db.scalar(select(Product).where(Product.name == "Latte"))
    return p.id, p.price_cents


def _body(db, qty: int = 1, method: str = "debito"):
    pid, price = _latte(db)
    return {"items": [{"product_id": pid, "qty": qty}], "channel": "salon", "payments": [{"method": method, "amount_cents": qty * price}]}


def _count(model) -> int:
    with SessionLocal() as s:
        return s.scalar(select(func.count()).select_from(model))


def test_the_same_sale_sent_twice_with_one_key_is_registered_once(seeded, db):
    client, admin = seeded
    body = _body(db)
    before = _count(Sale)
    a = client.post("/api/sales", json=body, headers={**admin, "Idempotency-Key": KEY})
    b = client.post("/api/sales", json=body, headers={**admin, "Idempotency-Key": KEY})
    assert a.status_code == b.status_code == 200
    assert a.json()["id"] == b.json()["id"] and a.json()["number"] == b.json()["number"]
    assert "idempotent-replay" not in a.headers and b.headers["idempotent-replay"] == "true"
    assert _count(Sale) == before + 1


def test_a_repeat_does_not_move_stock_or_cash_again(seeded, db):
    client, admin = seeded
    body = _body(db, qty=2, method="efectivo")

    def stock() -> float:
        with SessionLocal() as s:
            return sum(i.current_qty for i in s.scalars(select(StockItem)))

    cash0 = client.get("/api/cash/current", headers=admin).json()["expected_cash_cents"]
    client.post("/api/sales", json=body, headers={**admin, "Idempotency-Key": KEY})
    stock1, cash1 = stock(), client.get("/api/cash/current", headers=admin).json()["expected_cash_cents"]
    for _ in range(3):
        client.post("/api/sales", json=body, headers={**admin, "Idempotency-Key": KEY})
    assert stock() == stock1, "a repeat must not consume ingredients again"
    assert client.get("/api/cash/current", headers=admin).json()["expected_cash_cents"] == cash1 == cash0 + body["payments"][0]["amount_cents"]


def test_without_a_key_nothing_changes(seeded, db):
    """Existing clients (and the Pro modules) send no key: two identical sales are two sales, as always."""
    client, admin = seeded
    body = _body(db)
    before = _count(Sale)
    assert client.post("/api/sales", json=body, headers=admin).status_code == 200
    assert client.post("/api/sales", json=body, headers=admin).status_code == 200
    assert _count(Sale) == before + 2


def test_a_key_reused_for_another_request_is_refused(seeded, db):
    client, admin = seeded
    assert client.post("/api/sales", json=_body(db, qty=1), headers={**admin, "Idempotency-Key": KEY}).status_code == 200
    other = client.post("/api/sales", json=_body(db, qty=2), headers={**admin, "Idempotency-Key": KEY})
    assert other.status_code == 409, other.text
    # the same key from another user is never answered with someone else's sale
    cashier = login(client, "Caja Demo", "1111")
    stolen = client.post("/api/sales", json=_body(db, qty=1), headers={**cashier, "Idempotency-Key": KEY})
    assert stolen.status_code == 409, stolen.text
    # and the key is scoped: a cash movement cannot reuse a sale's key to read it
    mv = client.post("/api/cash/movements", json={"type": "in", "amount_cents": 100, "reason": "x"}, headers={**admin, "Idempotency-Key": KEY})
    assert mv.status_code == 409, mv.text


@pytest.mark.parametrize("bad", ["short", "x" * 65, "con espacios en la clave!!", "a;b" * 8, "../../etc/passwd" * 2, "'; DROP TABLE sales;--" + "x" * 10])
def test_malformed_keys_are_rejected_before_anything_happens(seeded, db, bad):
    client, admin = seeded
    before = _count(Sale)
    r = client.post("/api/sales", json=_body(db), headers={**admin, "Idempotency-Key": bad})
    assert r.status_code == 400, r.text
    assert _count(Sale) == before


def test_a_failed_attempt_does_not_use_up_the_key(seeded, db):
    """Underpaid sale -> 400 and nothing saved; fixing it and retrying with the SAME key works."""
    client, admin = seeded
    bad = _body(db)
    bad["payments"][0]["amount_cents"] -= 1
    assert client.post("/api/sales", json=bad, headers={**admin, "Idempotency-Key": KEY}).status_code == 400
    with SessionLocal() as s:
        assert s.get(IdempotencyKey, KEY) is None
    assert client.post("/api/sales", json=_body(db), headers={**admin, "Idempotency-Key": KEY}).status_code == 200


def test_simultaneous_repeats_create_one_sale(seeded, db):
    """Double click: several requests with the same key at the same moment -> one sale, everybody gets it."""
    client, admin = seeded
    body = _body(db)
    before = _count(Sale)
    results: list[tuple[int, int | None]] = []
    lock = threading.Lock()

    def fire():
        c = TestClient(create_app(run_lifespan=False))
        h = login(c, "Admin", "0000")
        r = c.post("/api/sales", json=body, headers={**h, "Idempotency-Key": KEY})
        with lock:
            results.append((r.status_code, r.json().get("id") if r.status_code == 200 else None))

    threads = [threading.Thread(target=fire) for _ in range(8)]
    [t.start() for t in threads]
    [t.join(timeout=60) for t in threads]
    assert len(results) == 8 and all(code == 200 for code, _ in results), results
    assert len({i for _, i in results}) == 1, "every repeat must return the same sale"
    assert _count(Sale) == before + 1


def test_a_cash_movement_repeat_is_recorded_once(seeded):
    client, admin = seeded
    body = {"type": "out", "amount_cents": 150000, "reason": "Proveedor"}
    before = _count(CashMovement)
    a = client.post("/api/cash/movements", json=body, headers={**admin, "Idempotency-Key": KEY})
    b = client.post("/api/cash/movements", json=body, headers={**admin, "Idempotency-Key": KEY})
    assert a.status_code == b.status_code == 200 and a.json()["id"] == b.json()["id"]
    assert b.headers["idempotent-replay"] == "true"
    assert _count(CashMovement) == before + 1


def test_an_account_payment_repeat_is_recorded_once(seeded, db):
    client, admin = seeded
    with SessionLocal() as s:
        c = s.scalar(select(Customer).where(Customer.balance_cents > 0).limit(1)) or s.scalar(select(Customer).limit(1))
        if c.balance_cents <= 0:  # give the customer a debt to pay
            c.balance_cents = 500000
            s.commit()
        cid, owed = c.id, c.balance_cents
    amount = min(100000, owed // 3)
    before = _count(CustomerAccountMovement)
    h = {**admin, "Idempotency-Key": KEY}
    a = client.post(f"/api/customers/{cid}/payments", json={"amount_cents": amount, "method": "efectivo"}, headers=h)
    b = client.post(f"/api/customers/{cid}/payments", json={"amount_cents": amount, "method": "efectivo"}, headers=h)
    assert a.status_code == b.status_code == 200, (a.text, b.text)
    assert a.json()["id"] == b.json()["id"]
    assert _count(CustomerAccountMovement) == before + 1
    with SessionLocal() as s:
        assert s.get(Customer, cid).balance_cents == owed - amount, "the debt must drop once, not twice"


def test_old_keys_are_pruned(seeded, db):
    client, admin = seeded
    with SessionLocal() as s:
        s.add(IdempotencyKey(key="old-" + "z" * 20, scope="sale", user_id=1, body_hash="x", resource_id=1, created_at=utcnow() - timedelta(days=30)))
        s.commit()
    assert client.post("/api/sales", json=_body(db), headers={**admin, "Idempotency-Key": KEY}).status_code == 200
    with SessionLocal() as s:
        assert s.get(IdempotencyKey, "old-" + "z" * 20) is None, "keys older than the retention are removed"
        assert s.get(IdempotencyKey, KEY) is not None
