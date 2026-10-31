"""Courtesy sales ("invita la casa"): stock moves like a sale, money doesn't."""

import pytest
from sqlalchemy import select

from app.main import bloom_pro
from app.models import AuditLog, Customer, LoyaltyTransaction, Product, Sale, StockItem, StockMovement
from app.services.timeutil import local_today
from tests.conftest import login

LATTE = 340000


def _pid(db, name: str) -> int:
    return db.scalar(select(Product.id).where(Product.name == name))


def _stock(db, name: str) -> float:
    db.expire_all()
    return db.scalar(select(StockItem.current_qty).where(StockItem.name == name))


def _customer(db, prefix: str) -> Customer:
    db.expire_all()
    return db.scalar(select(Customer).where(Customer.name.like(f"{prefix}%")))


def _courtesy(db, qty: int = 1, **kw) -> dict:
    return {"items": [{"product_id": _pid(db, "Latte"), "qty": qty}], "channel": "salon", "payments": [],
            "is_courtesy": True, **kw}


def test_courtesy_moves_stock_charges_nothing_and_is_audited(seeded, db):
    client, _ = seeded
    cajero = login(client, "Caja Demo", "1111")  # any cashier can give a courtesy
    leche0, cafe0 = _stock(db, "Leche entera"), _stock(db, "Café blend de la casa")
    r = client.post("/api/sales", json=_courtesy(db, qty=2, courtesy_reason="  Proveedor de leche "), headers=cajero)
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["is_courtesy"] is True and s["status"] == "completed"
    assert s["total_cents"] == 0 and s["subtotal_cents"] == 0 and s["discount_cents"] == 0
    assert s["courtesy_cents"] == 2 * LATTE and s["courtesy_reason"] == "Proveedor de leche"
    assert s["payments"] == [] and s["cost_cents"] > 0
    item = s["items"][0]
    assert (item["unit_price_cents"], item["discount_cents"], item["total_cents"]) == (LATTE, 2 * LATTE, 0)
    # Stock: exactly like a sale (200 ml milk + 18 g coffee per latte).
    assert _stock(db, "Leche entera") == leche0 - 400
    assert _stock(db, "Café blend de la casa") == cafe0 - 36
    mv = db.scalars(select(StockMovement).where(StockMovement.ref_type == "sale", StockMovement.ref_id == s["id"])).all()
    assert mv and all(m.type == "sale" and m.reason.startswith("Cortesía") for m in mv)
    log = db.scalar(select(AuditLog).where(AuditLog.entity == "sale", AuditLog.entity_id == s["id"]))
    assert log.action == "courtesy" and log.payload["courtesy_cents"] == 2 * LATTE
    assert log.user_id == s["user_id"] and s["user_name"] == "Caja Demo"


def test_courtesy_rejects_payments_discounts_and_points(seeded, db):
    client, admin = seeded
    bad = [
        _courtesy(db, payments=[{"method": "efectivo", "amount_cents": LATTE}]),
        _courtesy(db, discount_cents=1000),
        _courtesy(db, customer_id=_customer(db, "Estudiante").id, points_to_redeem=100),
    ]
    n0 = db.query(Sale).count()
    for body in bad:
        assert client.post("/api/sales", json=body, headers=admin).status_code == 400
    assert db.query(Sale).count() == n0


def test_courtesy_earns_no_points_and_no_account_charge(seeded, db):
    client, admin = seeded
    cust = _customer(db, "Vecina")
    points0, balance0 = cust.points, cust.balance_cents
    r = client.post("/api/sales", json=_courtesy(db, qty=3, customer_id=cust.id), headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["points_earned"] == 0 and r.json()["customer_name"]
    cust = _customer(db, "Vecina")
    assert (cust.points, cust.balance_cents) == (points0, balance0)
    assert not db.scalars(select(LoyaltyTransaction).where(LoyaltyTransaction.sale_id == r.json()["id"])).all()


def test_cash_expected_unchanged_and_z_report_lists_courtesies(seeded, db):
    client, admin = seeded
    before = client.get("/api/cash/current", headers=admin).json()
    paid = client.post("/api/sales", json={"items": [{"product_id": _pid(db, "Latte"), "qty": 1}], "channel": "salon",
                                           "payments": [{"method": "efectivo", "amount_cents": LATTE}]}, headers=admin)
    assert paid.status_code == 200
    for qty in (1, 2):
        assert client.post("/api/sales", json=_courtesy(db, qty=qty), headers=admin).status_code == 200
    cur = client.get("/api/cash/current", headers=admin).json()
    # Only the paid latte moves money/tickets; courtesies are a separate line.
    assert cur["expected_cash_cents"] == before["expected_cash_cents"] + LATTE
    assert cur["sales_total_cents"] == before["sales_total_cents"] + LATTE
    assert cur["tickets"] == before["tickets"] + 1
    assert cur["discounts_cents"] == before["discounts_cents"]
    assert (cur["courtesy_count"], cur["courtesy_cents"]) == (before["courtesy_count"] + 2, before["courtesy_cents"] + 3 * LATTE)

    z = client.post("/api/cash/close", json={"counts": []}, headers=admin)
    assert z.status_code == 200, z.text
    zj = z.json()
    assert zj["courtesy_count"] == cur["courtesy_count"] and zj["courtesy_cents"] == cur["courtesy_cents"]
    assert zj["sales_total_cents"] == cur["sales_total_cents"] and zj["tickets"] == cur["tickets"]
    cash = next(m for m in zj["by_method"] if m["method"] == "efectivo")
    assert cash["expected_cents"] == cur["expected_cash_cents"]
    hist = next(h for h in client.get("/api/cash/sessions", headers=admin).json() if h["id"] == zj["id"])
    assert hist["tickets"] == cur["tickets"]


def test_void_courtesy_restores_stock(seeded, db):
    client, admin = seeded
    leche0 = _stock(db, "Leche entera")
    s = client.post("/api/sales", json=_courtesy(db, qty=2), headers=admin).json()
    assert _stock(db, "Leche entera") == leche0 - 400
    enc = login(client, "Encargado Demo", "3333")
    r = client.post(f"/api/sales/{s['id']}/void", json={"reason": "Se cargó de más"}, headers=enc)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "voided" and r.json()["is_courtesy"] is True
    assert _stock(db, "Leche entera") == leche0
    cur = client.get("/api/cash/current", headers=admin).json()
    assert cur["courtesy_count"] == 0


def test_sales_list_flags_and_filters_courtesies(seeded, db):
    client, admin = seeded
    s = client.post("/api/sales", json=_courtesy(db), headers=admin).json()
    lst = client.get("/api/sales", params={"status": "courtesy"}, headers=admin).json()
    assert [i["id"] for i in lst["items"]] == [s["id"]]
    assert lst["items"][0]["is_courtesy"] and lst["items"][0]["courtesy_cents"] == LATTE
    assert lst["sum_total_cents"] == 0


def test_dashboard_and_customer_metrics_exclude_courtesy(seeded, db):
    client, admin = seeded
    today = local_today().isoformat()
    q = {"from": today, "to": today}
    cust = _customer(db, "Vecina")
    d0 = client.get("/api/dashboard", params=q, headers=admin).json()
    m0 = client.get(f"/api/customers/{cust.id}", headers=admin).json()
    assert client.post("/api/sales", json=_courtesy(db, qty=4, customer_id=cust.id), headers=admin).status_code == 200
    d1 = client.get("/api/dashboard", params=q, headers=admin).json()
    m1 = client.get(f"/api/customers/{cust.id}", headers=admin).json()
    for k in ("sales_cents", "tickets", "avg_ticket_cents", "gross_margin_cents"):
        assert d1["kpis"][k] == d0["kpis"][k], k
    assert d1["top_products"] == d0["top_products"]
    assert m1 == m0


@pytest.mark.skipif(not bloom_pro, reason="Pro reports not linked")
def test_pro_revenue_reports_exclude_courtesy(seeded, db):
    client, admin = seeded
    today = local_today().isoformat()
    q = {"from": today, "to": today}

    def snap():
        return {
            g: client.get("/api/reports/sales", params={**q, "group_by": g}, headers=admin).json()["totals"]
            for g in ("day", "product", "payment")
        } | {
            "products": client.get("/api/reports/products", params=q, headers=admin).json()["totals"],
            "cash": client.get("/api/reports/cash-sessions", params=q, headers=admin).json()["totals"],
        }

    before = snap()
    assert client.post("/api/sales", json=_courtesy(db, qty=5), headers=admin).status_code == 200
    assert snap() == before
