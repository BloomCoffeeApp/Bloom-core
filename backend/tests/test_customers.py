from datetime import timedelta

from app.db import SessionLocal
from app.models import Customer, CustomerAccountMovement, Sale, SaleItem, utcnow
from tests.conftest import login


def _new_customer(client, headers, **kw):
    body = {"name": "Juana Pérez", "phone": "11 4444-1234", "email": "juana@example.com", **kw}
    r = client.post("/api/customers", json=body, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _add_sale(db, number, customer_id, total, items, days_ago=0, status="completed"):
    s = Sale(number=number, customer_id=customer_id, total_cents=total, subtotal_cents=total,
             status=status, ts=utcnow() - timedelta(days=days_ago))
    s.items = [SaleItem(name_snapshot=n, qty=q, unit_price_cents=p, total_cents=int(q * p)) for n, q, p in items]
    db.add(s)


def test_search_and_pos_contract(seeded):
    client, h = seeded
    cajero = login(client, "Caja Demo", "1111")
    created = _new_customer(client, cajero)
    for key in ("id", "name", "phone", "email", "points", "balance_cents", "credit_limit_cents", "notes"):
        assert key in created

    by_name = client.get("/api/customers", params={"q": "juana"}, headers=cajero).json()
    assert [c["id"] for c in by_name] == [created["id"]]
    by_phone = client.get("/api/customers", params={"q": "44441234"}, headers=cajero).json()
    assert by_phone and by_phone[0]["id"] == created["id"]
    by_email = client.get("/api/customers", params={"q": "juana@"}, headers=cajero).json()
    assert by_email[0]["id"] == created["id"]

    # Duplicate phone rejected; barista cannot access customers
    r = client.post("/api/customers", json={"name": "Otra", "phone": "11 4444-1234"}, headers=cajero)
    assert r.status_code == 409
    barista = login(client, "Barista Demo", "2222")
    assert client.get("/api/customers", headers=barista).status_code == 403

    # Deactivated customers disappear from search
    assert client.delete(f"/api/customers/{created['id']}", headers=h).status_code == 200
    assert client.get("/api/customers", params={"q": "juana"}, headers=cajero).json() == []


def test_metrics_and_segments(seeded):
    client, h = seeded
    c = _new_customer(client, h)
    other = _new_customer(client, h, name="Viejo Cliente", phone="11 0000-0000", email=None)
    with SessionLocal() as db:
        _add_sale(db, 9001, c["id"], 300000, [("Latte", 2, 150000)], days_ago=1)
        _add_sale(db, 9002, c["id"], 100000, [("Latte", 1, 100000)], days_ago=3)
        _add_sale(db, 9003, c["id"], 200000, [("Medialuna", 1, 50000), ("Latte", 1, 150000)], days_ago=5)
        _add_sale(db, 9004, c["id"], 400000, [("Tostado", 4, 100000)], days_ago=7)
        _add_sale(db, 9005, c["id"], 999999, [("Torta", 10, 99999)], days_ago=2, status="voided")
        _add_sale(db, 9006, other["id"], 50000, [("Café", 1, 50000)], days_ago=60)
        db.commit()

    d = client.get(f"/api/customers/{c['id']}", headers=h).json()
    m = d["metrics"]
    assert m["tickets"] == 4
    assert m["total_spent_cents"] == 1000000
    assert m["avg_ticket_cents"] == 250000
    assert m["days_since_last_visit"] in (0, 1, 2)
    assert m["favorite_product"]["name"] in ("Latte", "Tostado")  # 4 each
    assert m["visits_30d"] == 4

    sales = client.get(f"/api/customers/{c['id']}/sales", params={"page_size": 2}, headers=h).json()
    assert sales["total"] == 5 and len(sales["items"]) == 2

    seg = lambda s: {x["id"] for x in client.get("/api/customers", params={"segment": s}, headers=h).json()}  # noqa: E731
    assert c["id"] in seg("frecuentes") and other["id"] not in seg("frecuentes")
    assert other["id"] in seg("inactivos") and c["id"] not in seg("inactivos")
    birthday_ids = seg("cumpleanos_mes")
    demo_bday = next(x for x in client.get("/api/customers", params={"q": "Frecuente"}, headers=h).json())
    assert demo_bday["id"] in birthday_ids

    stats = client.get("/api/customers/stats", headers=h).json()
    assert stats["activos_30d"] >= 1
    assert any(b["id"] == demo_bday["id"] for b in stats["cumpleanos_hoy"])


def test_account_payment_and_overpay(seeded):
    client, h = seeded
    c = _new_customer(client, h, credit_limit_cents=1000000)
    with SessionLocal() as db:
        cust = db.get(Customer, c["id"])
        cust.balance_cents = 500000
        db.add(CustomerAccountMovement(customer_id=c["id"], amount_cents=500000, type="charge"))
        db.commit()

    r = client.post(f"/api/customers/{c['id']}/payments", json={"amount_cents": 600000, "method": "efectivo"}, headers=h)
    assert r.status_code == 400
    r = client.post(f"/api/customers/{c['id']}/payments", json={"amount_cents": 200000, "method": "transferencia"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["amount_cents"] == -200000 and r.json()["type"] == "payment"
    d = client.get(f"/api/customers/{c['id']}", headers=h).json()
    assert d["balance_cents"] == 300000
    assert len(d["account_movements"]) == 2

    debtors = client.get("/api/customers", params={"segment": "deudores"}, headers=h).json()
    assert c["id"] in [x["id"] for x in debtors]
    assert all(x["balance_cents"] > 0 for x in debtors)

    r = client.post(f"/api/customers/{c['id']}/payments", json={"amount_cents": 300000, "method": "efectivo"}, headers=h)
    assert r.status_code == 200
    r = client.post(f"/api/customers/{c['id']}/payments", json={"amount_cents": 1, "method": "efectivo"}, headers=h)
    assert r.status_code == 400


def test_points_adjust_requires_manager(seeded):
    client, h = seeded
    c = _new_customer(client, h)
    cajero = login(client, "Caja Demo", "1111")
    body = {"points": 50, "reason": "Bienvenida"}
    assert client.post(f"/api/customers/{c['id']}/points", json=body, headers=cajero).status_code == 403
    encargado = login(client, "Encargado Demo", "3333")
    assert client.post(f"/api/customers/{c['id']}/points", json=body, headers=encargado).status_code == 200
    r = client.post(f"/api/customers/{c['id']}/points", json={"points": -80, "reason": "x"}, headers=encargado)
    assert r.status_code == 400
    d = client.get(f"/api/customers/{c['id']}", headers=h).json()
    assert d["points"] == 50 and d["loyalty_transactions"][0]["points"] == 50
    # cajero cannot change the credit limit
    r = client.patch(f"/api/customers/{c['id']}", json={"credit_limit_cents": 100}, headers=cajero)
    assert r.status_code == 403
    r = client.patch(f"/api/customers/{c['id']}", json={"notes": "Cortado en jarrito"}, headers=cajero)
    assert r.status_code == 200 and r.json()["notes"] == "Cortado en jarrito"
