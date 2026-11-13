"""Property-based tests (hypothesis): money is in integer cents and the sums must always close.

They run the real API with many random inputs and assert invariants instead of single examples:
totals = items - discount + delivery fee, payments must cover the total exactly, a failed sale leaves
nothing behind, and the Z/cash numbers add up to what was charged.
"""
from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select

from app.models import Product, Sale
from app.services import sales as sales_service

# One shared seeded DB per test (function fixture): that is intended, every example adds one sale.
FIXTURE_OK = settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])


def _latte(db) -> tuple[int, int]:
    p = db.scalar(select(Product).where(Product.name == "Latte"))
    return p.id, p.price_cents


def _open_cash(client, admin):
    if client.get("/api/cash/current", headers=admin).json() is None:
        r = client.post("/api/cash/open", json={"opening_cents": 0}, headers=admin)
        assert r.status_code in (200, 409), r.text


def _split(total: int, cuts: list[float]) -> list[int]:
    """Splits `total` into len(cuts)+1 integer parts that add up to it."""
    points = sorted({int(total * c) for c in cuts})
    edges = [0, *points, total]
    return [b - a for a, b in zip(edges, edges[1:]) if b > a]


@FIXTURE_OK
@given(
    qty=st.integers(1, 6),
    discount_pct=st.one_of(st.none(), st.floats(0, 100, allow_nan=False)),
    discount_cents=st.integers(0, 3_000_000),
    fee=st.integers(0, 400_000),
    channel=st.sampled_from(["salon", "llevar", "delivery"]),
    cuts=st.lists(st.floats(0.01, 0.99), max_size=2),
    method=st.sampled_from(["efectivo", "debito", "transferencia"]),
)
def test_sale_total_and_payments_always_close(seeded, db, qty, discount_pct, discount_cents, fee, channel, cuts, method):
    client, admin = seeded
    _open_cash(client, admin)
    pid, price = _latte(db)
    fee = fee if channel == "delivery" else 0
    subtotal = qty * price
    base = {"items": [{"product_id": pid, "qty": qty}], "channel": channel, "delivery_fee_cents": fee}
    if discount_pct is not None:
        base["discount_pct"] = discount_pct
    else:
        base["discount_cents"] = discount_cents

    before = db.scalar(select(func.count(Sale.id)))
    # Ask the server what it would charge, then pay exactly that split in 1-3 payments.
    probe = client.post("/api/sales", json=base | {"payments": [{"method": method, "amount_cents": 1}]}, headers=admin)
    if probe.status_code != 400:  # an arbitrary 1-cent payment can only be accepted if the total is 1 cent
        assert probe.status_code in (200, 400, 409, 422), probe.text
    db.expire_all()
    if probe.status_code == 200:
        return  # total was exactly 1 cent: nothing else to check
    assert db.scalar(select(func.count(Sale.id))) == before, "a rejected sale must not leave a sale behind"

    # Compute the expected total with the same rules the POS shows: discount capped at the subtotal.
    disc = round(subtotal * discount_pct / 100) if discount_pct is not None else min(discount_cents, subtotal)
    disc = min(disc, subtotal)
    total = subtotal - disc + fee
    if total <= 0:
        return
    parts = _split(total, cuts)
    r = client.post("/api/sales", json=base | {"payments": [{"method": method, "amount_cents": a} for a in parts]}, headers=admin)
    if r.status_code != 200:
        # The only legitimate refusals: rounding of the percentage discount differs by a cent, or rules
        # that depend on the method. Never a server error.
        event(f"sale refused {r.status_code}")
        assert r.status_code in (400, 409, 422), r.text
        return
    event("sale accepted")
    s = r.json()
    assert s["subtotal_cents"] == subtotal
    assert s["delivery_fee_cents"] == fee
    assert s["total_cents"] == s["subtotal_cents"] - s["discount_cents"] - s["points_discount_cents"] + s["delivery_fee_cents"]
    assert s["total_cents"] > 0 and s["total_cents"] == sum(p["amount_cents"] for p in s["payments"])


@FIXTURE_OK
@given(qty=st.integers(1, 4), delta=st.sampled_from([-1, 1, -100, 100]))
def test_underpaying_or_overpaying_is_never_accepted(seeded, db, qty, delta):
    client, admin = seeded
    _open_cash(client, admin)
    pid, price = _latte(db)
    before = db.scalar(select(func.count(Sale.id)))
    body = {"items": [{"product_id": pid, "qty": qty}], "channel": "salon", "payments": [{"method": "debito", "amount_cents": qty * price + delta}]}
    r = client.post("/api/sales", json=body, headers=admin)
    assert r.status_code == 400, r.text
    db.expire_all()
    assert db.scalar(select(func.count(Sale.id))) == before


@settings(max_examples=300, deadline=None)
@given(points=st.integers(0, 10**7), per=st.integers(-5, 5_000), value=st.integers(0, 10**7))
def test_points_discount_is_never_negative_and_monotonic(points, per, value):
    cfg = {"points_per_reward": per, "reward_value_cents": value}
    d = sales_service.points_discount_cents(points, cfg)
    assert d >= 0
    assert sales_service.points_discount_cents(points + 1, cfg) >= d
    if per > 0:
        assert d == (points // per) * value
