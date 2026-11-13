"""Several cashiers selling at the same time (SQLite WAL + threads): nothing may fail with 'database is locked',
ticket numbers must stay unique and the cash numbers must add up to exactly what was charged."""
import threading
from collections import Counter

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import SessionLocal
from app.main import create_app
from app.models import Order, Product, Sale
from app.services.orders import day_bounds_utc, local_today, now
from tests.conftest import login

THREADS, SALES_EACH = 6, 8


def test_concurrent_sales_have_unique_numbers_and_consistent_totals(seeded):
    client, admin = seeded
    with SessionLocal() as s:
        latte = s.scalar(select(Product).where(Product.name == "Latte"))
        pid, price = latte.id, latte.price_cents
        before = s.scalar(select(func.count(Sale.id)))
        before_total = s.scalar(select(func.coalesce(func.sum(Sale.total_cents), 0)).where(Sale.status == "completed"))

    results: list[tuple[int, int | None]] = []
    lock = threading.Lock()

    def cashier(n: int):
        c = TestClient(create_app(run_lifespan=False))
        h = login(c, "Admin", "0000")
        for i in range(SALES_EACH):
            qty = 1 + (n + i) % 3
            r = c.post("/api/sales", json={"items": [{"product_id": pid, "qty": qty}], "channel": "salon",
                                           "payments": [{"method": "debito", "amount_cents": qty * price}]}, headers=h)
            with lock:
                results.append((r.status_code, r.json().get("number") if r.status_code == 200 else None))
                if r.status_code != 200:
                    results.append((r.status_code, r.text))  # type: ignore[arg-type]

    threads = [threading.Thread(target=cashier, args=(n,)) for n in range(THREADS)]
    [t.start() for t in threads]
    [t.join(timeout=120) for t in threads]

    bad = [r for r in results if r[0] != 200]
    assert not bad, f"failed sales under concurrency: {bad[:5]}"
    assert len(results) == THREADS * SALES_EACH
    numbers = [n for _, n in results]
    dupes = [n for n, c in Counter(numbers).items() if c > 1]
    assert not dupes, f"duplicated ticket numbers: {dupes}"

    with SessionLocal() as s:
        assert s.scalar(select(func.count(Sale.id))) == before + THREADS * SALES_EACH
        after_total = s.scalar(select(func.coalesce(func.sum(Sale.total_cents), 0)).where(Sale.status == "completed"))
    with SessionLocal() as s:  # the bar screen numbers (#1, #2...) must not repeat within the day either
        a, b = day_bounds_utc(local_today())
        order_numbers = list(s.scalars(select(Order.number).where(Order.created_at >= a, Order.created_at < b)))
    assert len(order_numbers) == len(set(order_numbers)), f"repeated order numbers: {Counter(order_numbers).most_common(3)}"
    expected = sum((1 + (n + i) % 3) * price for n in range(THREADS) for i in range(SALES_EACH))
    assert after_total - before_total == expected, "the cash taken must equal what was charged, to the cent"
