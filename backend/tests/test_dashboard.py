from datetime import date, datetime

import pytest
from sqlalchemy import select

from app.models import Product, Sale, SaleItem, SalePayment, StockItem, User
from app.services import stock as stock_svc
from tests.conftest import login

# Fixed past date so demo-generated sales (last 90 days) never overlap.
D = date(2025, 1, 15)  # Wednesday
PREV = date(2025, 1, 8)
Q = {"from": D.isoformat(), "to": D.isoformat()}


def _sale(db, number, ts, total, cost, items, payments, status="completed", user_id=None, channel="salon"):
    s = Sale(number=number, ts=ts, total_cents=total, subtotal_cents=total, cost_cents=cost, status=status,
             user_id=user_id, channel=channel)
    s.items = [
        SaleItem(product_id=p.id, name_snapshot=p.name, qty=q, unit_price_cents=t // q if q else t,
                 total_cents=t, cost_cents=c)
        for p, q, t, c in items
    ]
    s.payments = [SalePayment(method=m, amount_cents=a, tendered_cents=None) for m, a in payments]
    db.add(s)
    return s


@pytest.fixture()
def sales(seeded, db):
    client, admin = seeded
    a, b = db.scalars(select(Product).order_by(Product.id).limit(2)).all()
    uid = db.scalar(select(User.id).where(User.name == "Admin"))
    # Local 10:30 = 13:30 UTC (UTC-3).
    _sale(db, 900001, datetime(2025, 1, 15, 13, 30), 10000, 4000,
          [(a, 2, 6000, 2400), (b, 1, 4000, 1600)], [("efectivo", 10000)], user_id=uid)
    _sale(db, 900002, datetime(2025, 1, 15, 13, 45), 3000, 1200,
          [(a, 1, 3000, 1200)], [("debito", 2000), ("efectivo", 1000)], user_id=uid, channel="llevar")
    # Voided: must be ignored everywhere.
    _sale(db, 900003, datetime(2025, 1, 15, 14, 0), 99999, 0, [(a, 9, 99999, 0)], [("efectivo", 99999)], status="voided")
    # 01:00 UTC of the 16th is 22:00 local of the 15th → belongs to D.
    _sale(db, 900004, datetime(2025, 1, 16, 1, 0), 1000, 0, [(b, 1, 1000, 0)], [("efectivo", 1000)])
    # Same weekday previous week.
    _sale(db, 900005, datetime(2025, 1, 8, 13, 30), 6500, 2000, [(a, 1, 6500, 2000)], [("efectivo", 6500)])
    db.commit()
    return client, admin, a, b


def test_dashboard_kpis_and_comparison(sales):
    client, admin, a, _b = sales
    r = client.get("/api/dashboard", params=Q, headers=admin)
    assert r.status_code == 200, r.text
    d = r.json()
    k = d["kpis"]
    assert k["sales_cents"] == 14000
    assert k["tickets"] == 3
    assert k["avg_ticket_cents"] == 4667
    assert k["gross_margin_cents"] == 14000 - 5200
    assert k["margin_pct"] == pytest.approx(62.9, abs=0.05)
    assert d["compare_from"] == PREV.isoformat()
    assert d["previous"]["sales_cents"] == 6500
    assert d["deltas"]["sales_cents"] == pytest.approx(115.4, abs=0.05)
    assert d["deltas"]["tickets"] == pytest.approx(200.0)
    hours = {h["hour"]: h for h in d["hourly"]}
    assert hours[10]["sales_cents"] == 13000
    assert hours[10]["avg_cents"] == 6500 // 4  # avg of 4 previous same weekdays
    assert hours[22]["sales_cents"] == 1000
    assert len(d["daily"]) == 30 and d["daily"][-1]["sales_cents"] == 14000
    assert d["top_products"][0]["product_id"] == a.id
    pay = {p["key"]: p["sales_cents"] for p in d["payment_mix"]}
    assert pay == {"efectivo": 12000, "debito": 2000}
    ch = {c["key"]: c["sales_cents"] for c in d["channel_mix"]}
    assert ch == {"salon": 11000, "llevar": 3000}
    assert len(d["recent_sales"]) >= 5


def test_dashboard_hides_costs_for_cashier_and_barista(sales):
    client, *_ = sales
    for name, pin in (("Caja Demo", "1111"), ("Barista Demo", "2222")):
        h = login(client, name, pin)
        d = client.get("/api/dashboard", params=Q, headers=h).json()
        assert d["show_costs"] is False
        assert d["kpis"]["gross_margin_cents"] is None
        assert d["kpis"]["margin_pct"] is None
        assert d["kpis"]["sales_cents"] == 14000


def test_dashboard_requires_login(client):
    assert client.get("/api/dashboard").status_code == 401
