from sqlalchemy import func, select

from app.models import (
    CashSession,
    Customer,
    CustomerAccountMovement,
    LoyaltyTransaction,
    Modifier,
    Product,
    Sale,
    StockItem,
)
from tests.conftest import login


def _pid(db, name: str) -> int:
    return db.scalar(select(Product.id).where(Product.name == name))


def _mod(db, name: str) -> int:
    return db.scalar(select(Modifier.id).where(Modifier.name == name))


def _stock(db, name: str) -> float:
    db.expire_all()
    return db.scalar(select(StockItem.current_qty).where(StockItem.name == name))


def _customer(db, name_prefix: str) -> Customer:
    db.expire_all()
    return db.scalar(select(Customer).where(Customer.name.like(f"{name_prefix}%")))


def _sale_body(db, *, payments, items=None, **kw):
    return {"items": items or [{"product_id": _pid(db, "Latte"), "qty": 1}], "channel": "salon", "payments": payments, **kw}


LATTE = 340000
AVENA = 60000


def test_sale_is_atomic_and_uses_recipe_plus_modifier(seeded, db):
    client, admin = seeded
    before = {n: _stock(db, n) for n in ("Leche entera", "Bebida de avena", "Café blend de la casa", "Vaso térmico 12oz")}
    body = _sale_body(
        db,
        items=[{"product_id": _pid(db, "Latte"), "qty": 2, "modifier_ids": [_mod(db, "Bebida de avena")], "notes": "bien caliente"}],
        payments=[{"method": "debito", "amount_cents": 2 * (LATTE + AVENA)}],
    )
    r = client.post("/api/sales", json=body, headers=admin)
    assert r.status_code == 200, r.text
    sale = r.json()
    assert sale["total_cents"] == 2 * (LATTE + AVENA)
    assert sale["items"][0]["unit_price_cents"] == LATTE + AVENA
    assert sale["items"][0]["modifiers"][0]["name"] == "Bebida de avena"
    assert sale["cost_cents"] > 0
    # Avena replaces 200 ml of milk per latte: milk unchanged, avena −400, coffee −36, cups −2.
    assert _stock(db, "Leche entera") == before["Leche entera"]
    assert _stock(db, "Bebida de avena") == before["Bebida de avena"] - 400
    assert _stock(db, "Café blend de la casa") == before["Café blend de la casa"] - 36
    assert _stock(db, "Vaso térmico 12oz") == before["Vaso térmico 12oz"] - 2


def test_price_comes_from_backend_and_modifier_validation(seeded, db):
    client, admin = seeded
    # Modifier from a group not linked to Medialuna is rejected.
    body = _sale_body(db, items=[{"product_id": _pid(db, "Medialuna"), "modifier_ids": [_mod(db, "Shot extra")]}],
                      payments=[{"method": "debito", "amount_cents": 90000}])
    assert client.post("/api/sales", json=body, headers=admin).status_code == 400


def test_split_payment(seeded, db):
    client, admin = seeded
    body = _sale_body(db, payments=[{"method": "efectivo", "amount_cents": 140000, "tendered_cents": 200000},
                                    {"method": "qr", "amount_cents": 200000}])
    r = client.post("/api/sales", json=body, headers=admin)
    assert r.status_code == 200, r.text
    pays = {p["method"]: p for p in r.json()["payments"]}
    assert pays["efectivo"]["change_cents"] == 60000
    assert pays["qr"]["amount_cents"] == 200000
    assert r.json()["change_cents"] == 60000


def test_payments_must_match_total_and_nothing_is_written(seeded, db):
    client, admin = seeded
    db.expire_all()
    n_before = db.scalar(select(func.count(Sale.id)))
    leche = _stock(db, "Leche entera")
    for pays in ([{"method": "debito", "amount_cents": LATTE - 1}], [{"method": "debito", "amount_cents": LATTE + 1}], []):
        r = client.post("/api/sales", json=_sale_body(db, payments=pays), headers=admin)
        assert r.status_code == 400
    db.expire_all()
    assert db.scalar(select(func.count(Sale.id))) == n_before
    assert _stock(db, "Leche entera") == leche


def test_change_only_on_cash(seeded, db):
    client, admin = seeded
    r = client.post("/api/sales", json=_sale_body(db, payments=[{"method": "efectivo", "amount_cents": LATTE, "tendered_cents": 1000000}]), headers=admin)
    assert r.status_code == 200
    assert r.json()["payments"][0]["change_cents"] == 1000000 - LATTE
    bad = client.post("/api/sales", json=_sale_body(db, payments=[{"method": "debito", "amount_cents": LATTE, "tendered_cents": 500000}]), headers=admin)
    assert bad.status_code == 400
    short = client.post("/api/sales", json=_sale_body(db, payments=[{"method": "efectivo", "amount_cents": LATTE, "tendered_cents": 100000}]), headers=admin)
    assert short.status_code == 400


def test_numbering_is_correlative_without_gaps(seeded, db):
    client, admin = seeded
    ok = [{"method": "debito", "amount_cents": LATTE}]
    n1 = client.post("/api/sales", json=_sale_body(db, payments=ok), headers=admin).json()["number"]
    assert client.post("/api/sales", json=_sale_body(db, payments=[{"method": "debito", "amount_cents": 1}]), headers=admin).status_code == 400
    n2 = client.post("/api/sales", json=_sale_body(db, payments=ok), headers=admin).json()["number"]
    n3 = client.post("/api/sales", json=_sale_body(db, payments=ok), headers=admin).json()["number"]
    assert (n2, n3) == (n1 + 1, n1 + 2)
    db.expire_all()
    assert db.scalar(select(func.max(Sale.number))) == db.scalar(select(func.count(Sale.id)))


def test_void_reverts_stock_points_and_keeps_sale(seeded, db):
    client, admin = seeded
    cust = _customer(db, "Vecina")
    points0 = cust.points
    leche0 = _stock(db, "Leche entera")
    body = _sale_body(db, customer_id=cust.id, payments=[{"method": "debito", "amount_cents": LATTE}])
    sale = client.post("/api/sales", json=body, headers=admin).json()
    assert sale["points_earned"] == LATTE // 100000  # 1 point each $1000
    assert _customer(db, "Vecina").points == points0 + sale["points_earned"]
    assert _stock(db, "Leche entera") == leche0 - 200

    cajero = login(client, "Caja Demo", "1111")
    assert client.post(f"/api/sales/{sale['id']}/void", json={"reason": "Error de carga"}, headers=cajero).status_code == 403
    enc = login(client, "Encargado Demo", "3333")
    r = client.post(f"/api/sales/{sale['id']}/void", json={"reason": "Error de carga"}, headers=enc)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "voided" and r.json()["voided_by_name"] == "Encargado Demo"
    assert _stock(db, "Leche entera") == leche0
    assert _customer(db, "Vecina").points == points0
    assert client.post(f"/api/sales/{sale['id']}/void", json={"reason": "otra vez"}, headers=enc).status_code == 409
    assert client.get(f"/api/sales/{sale['id']}", headers=admin).json()["status"] == "voided"
    lt = db.scalars(select(LoyaltyTransaction).where(LoyaltyTransaction.sale_id == sale["id"])).all()
    assert sum(t.points for t in lt) == 0


def test_points_redemption(seeded, db):
    client, admin = seeded
    cust = _customer(db, "Estudiante")
    cust.points = 150
    db.commit()
    # Must be a multiple of points_per_reward (100) and within balance.
    bad = _sale_body(db, customer_id=cust.id, points_to_redeem=50, payments=[{"method": "debito", "amount_cents": LATTE}])
    assert client.post("/api/sales", json=bad, headers=admin).status_code == 400
    too_many = _sale_body(db, customer_id=cust.id, points_to_redeem=200, payments=[{"method": "debito", "amount_cents": 0}])
    assert client.post("/api/sales", json=too_many, headers=admin).status_code == 400
    # 100 points = $5000 off, capped at a $3400 latte + $3400 latte = $6800 → pay $1800.
    items = [{"product_id": _pid(db, "Latte"), "qty": 2}]
    ok = _sale_body(db, items=items, customer_id=cust.id, points_to_redeem=100, payments=[{"method": "debito", "amount_cents": 2 * LATTE - 500000}])
    r = client.post("/api/sales", json=ok, headers=admin)
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["points_discount_cents"] == 500000 and s["total_cents"] == 2 * LATTE - 500000
    assert _customer(db, "Estudiante").points == 150 - 100 + s["points_earned"]
    enc = login(client, "Encargado Demo", "3333")
    client.post(f"/api/sales/{s['id']}/void", json={"reason": "prueba canje"}, headers=enc)
    assert _customer(db, "Estudiante").points == 150


def test_cuenta_corriente_with_limit(seeded, db):
    client, admin = seeded
    cust = _customer(db, "Oficina")
    assert cust.credit_limit_cents == 5000000
    cust.balance_cents = 4800000
    db.commit()
    cc = [{"method": "cuenta_corriente", "amount_cents": LATTE}]
    r = client.post("/api/sales", json=_sale_body(db, customer_id=cust.id, payments=cc), headers=admin)
    assert r.status_code == 400 and "límite" in r.json()["detail"]
    assert client.post("/api/sales", json=_sale_body(db, payments=cc), headers=admin).status_code == 400  # requires customer

    cust = _customer(db, "Oficina")
    cust.balance_cents = 1000000
    db.commit()
    r = client.post("/api/sales", json=_sale_body(db, customer_id=cust.id, payments=cc), headers=admin)
    assert r.status_code == 200, r.text
    assert _customer(db, "Oficina").balance_cents == 1000000 + LATTE
    mv = db.scalar(select(CustomerAccountMovement).where(CustomerAccountMovement.sale_id == r.json()["id"]))
    assert mv.type == "charge" and mv.amount_cents == LATTE
    enc = login(client, "Encargado Demo", "3333")
    client.post(f"/api/sales/{r.json()['id']}/void", json={"reason": "devolución"}, headers=enc)
    assert _customer(db, "Oficina").balance_cents == 1000000


def test_no_sale_without_open_cash(seeded, db):
    client, admin = seeded
    assert client.post("/api/cash/close", json={"counts": []}, headers=admin).status_code == 200
    r = client.post("/api/sales", json=_sale_body(db, payments=[{"method": "debito", "amount_cents": LATTE}]), headers=admin)
    assert r.status_code == 409
    assert "caja" in r.json()["detail"].lower()


def test_cashier_cannot_discount(seeded, db):
    client, _ = seeded
    cajero = login(client, "Caja Demo", "1111")
    r = client.post("/api/sales", json=_sale_body(db, discount_cents=10000, payments=[{"method": "debito", "amount_cents": LATTE - 10000}]), headers=cajero)
    assert r.status_code == 403 and "encargado" in r.json()["detail"]
    items = [{"product_id": _pid(db, "Latte"), "qty": 1, "discount_cents": 5000}]
    assert client.post("/api/sales", json=_sale_body(db, items=items, payments=[{"method": "debito", "amount_cents": LATTE - 5000}]), headers=cajero).status_code == 403
    # Cajero without discount works; encargado with discount (10%) works.
    assert client.post("/api/sales", json=_sale_body(db, payments=[{"method": "debito", "amount_cents": LATTE}]), headers=cajero).status_code == 200
    enc = login(client, "Encargado Demo", "3333")
    r = client.post("/api/sales", json=_sale_body(db, discount_pct=10, payments=[{"method": "debito", "amount_cents": LATTE - 34000}]), headers=enc)
    assert r.status_code == 200, r.text
    assert r.json()["discount_cents"] == 34000


def test_list_detail_and_ticket(seeded, db):
    client, admin = seeded
    sale = client.post("/api/sales", json=_sale_body(db, payments=[{"method": "qr", "amount_cents": LATTE}]), headers=admin).json()
    lst = client.get("/api/sales", params={"method": "qr", "page_size": 10}, headers=admin).json()
    assert lst["items"][0]["id"] == sale["id"] and lst["total"] > 1 and len(lst["items"]) == 10
    t = client.get(f"/api/sales/{sale['id']}/ticket", headers=admin).json()
    assert t["business"]["name"] == "Café Test" and t["sale"]["number"] == sale["number"]
    assert t["payment_names"]["qr"]
    assert client.get("/api/payment-methods", headers=admin).json()[0]["code"] == "efectivo"
    assert client.get("/api/sales/999999", headers=admin).status_code == 404


def test_demo_sales_history(seeded, db):
    db.expire_all()
    assert db.scalar(select(func.count(Sale.id))) > 90 * 50
    open_sessions = db.scalars(select(CashSession).where(CashSession.status == "open")).all()
    assert len(open_sessions) == 1
    assert db.scalar(select(func.count(Sale.id)).where(Sale.cash_session_id == open_sessions[0].id)) > 0
    closed = db.scalars(select(CashSession).where(CashSession.status == "closed")).all()
    assert len(closed) >= 90 and all(s.counts for s in closed[:5])
    for item in db.scalars(select(StockItem)):
        assert item.min_qty * 1.9 <= item.current_qty <= item.min_qty * 4.1, item.name
    client, admin = seeded
    cur = client.get("/api/cash/current", headers=admin).json()
    assert cur["tickets"] > 0 and cur["status"] == "open"


def test_payment_methods_toggle(seeded):
    client, h = seeded
    methods = client.get("/api/payment-methods", headers=h).json()
    assert methods and all(m["active"] for m in methods)
    target = next(m for m in methods if m["code"] != "cash")
    r = client.patch(f"/api/payment-methods/{target['id']}", json={"active": False}, headers=h)
    assert r.status_code == 200 and r.json()["active"] is False
    codes = {m["code"] for m in client.get("/api/payment-methods", headers=h).json()}
    assert target["code"] not in codes
    all_codes = {m["code"] for m in client.get("/api/payment-methods?include_inactive=true", headers=h).json()}
    assert target["code"] in all_codes
    # Can't disable the last enabled method
    for m in client.get("/api/payment-methods", headers=h).json()[:-1]:
        client.patch(f"/api/payment-methods/{m['id']}", json={"active": False}, headers=h)
    last = client.get("/api/payment-methods", headers=h).json()
    assert len(last) == 1
    r = client.patch(f"/api/payment-methods/{last[0]['id']}", json={"active": False}, headers=h)
    assert r.status_code == 400
    # Non-admins can't change them
    from tests.conftest import login

    hc = login(client, "Caja Demo", "1111")
    assert client.patch(f"/api/payment-methods/{target['id']}", json={"active": True}, headers=hc).status_code == 403


def test_delivery_fee_adds_to_total_and_payments(seeded, db):
    client, admin = seeded
    fee = 50000
    body = _sale_body(db, channel="delivery", delivery_fee_cents=fee, payments=[{"method": "debito", "amount_cents": LATTE + fee}])
    r = client.post("/api/sales", json=body, headers=admin)
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["delivery_fee_cents"] == fee and s["total_cents"] == LATTE + fee and s["subtotal_cents"] == LATTE
    assert client.get(f"/api/sales/{s['id']}", headers=admin).json()["delivery_fee_cents"] == fee
    # Paying only the items is not enough.
    short = _sale_body(db, channel="delivery", delivery_fee_cents=fee, payments=[{"method": "debito", "amount_cents": LATTE}])
    assert client.post("/api/sales", json=short, headers=admin).status_code == 400


def test_delivery_fee_only_on_delivery_and_not_courtesy(seeded, db):
    client, admin = seeded
    for channel in ("salon", "llevar"):
        body = _sale_body(db, channel=channel, delivery_fee_cents=50000, payments=[{"method": "debito", "amount_cents": LATTE + 50000}])
        r = client.post("/api/sales", json=body, headers=admin)
        assert r.status_code == 400 and "delivery" in r.json()["detail"]
    courtesy = _sale_body(db, channel="delivery", delivery_fee_cents=50000, is_courtesy=True, payments=[])
    assert client.post("/api/sales", json=courtesy, headers=admin).status_code == 400


def test_delivery_fee_is_excluded_from_points_and_discounts(seeded, db):
    client, admin = seeded
    cust = _customer(db, "Estudiante")
    base = client.post("/api/sales", json=_sale_body(db, channel="delivery", customer_id=cust.id,
                                                      payments=[{"method": "debito", "amount_cents": LATTE}]), headers=admin)
    assert base.status_code == 200, base.text
    fee = 1_000_000
    r = client.post("/api/sales", json=_sale_body(db, channel="delivery", customer_id=cust.id, delivery_fee_cents=fee,
                                                   payments=[{"method": "debito", "amount_cents": LATTE + fee}]), headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["points_earned"] == base.json()["points_earned"]
    # discount_pct applies to the items only.
    d = client.post("/api/sales", json=_sale_body(db, channel="delivery", delivery_fee_cents=fee, discount_pct=10,
                                                   payments=[{"method": "debito", "amount_cents": LATTE - round(LATTE * 0.1) + fee}]), headers=admin)
    assert d.status_code == 200, d.text
    assert d.json()["discount_cents"] == round(LATTE * 0.1) and d.json()["total_cents"] == LATTE - round(LATTE * 0.1) + fee
