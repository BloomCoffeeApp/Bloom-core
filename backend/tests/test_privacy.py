"""Personal data rights over the cafe's own data: anonymize, export, retention of online-order contacts."""

from datetime import timedelta

from app.db import SessionLocal
from app.models import AuditLog, Customer, LoyaltyTransaction, Order, Sale, SaleItem, utcnow
from app.services import privacy
from tests.conftest import login


def _customer(client, h, **kw):
    body = {"name": "Marta Gómez", "phone": "11 4444-7777", "email": "marta@example.com",
            "address": "Calle Falsa 123", "notes": "Alérgica al maní", **kw}
    r = client.post("/api/customers", json=body, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _sale_and_order(cid, number=9001):
    with SessionLocal() as db:
        s = Sale(number=number, customer_id=cid, total_cents=150000, subtotal_cents=150000, notes="Marta pidió sin hielo")
        s.items = [SaleItem(name_snapshot="Latte", qty=1, unit_price_cents=150000, total_cents=150000)]
        db.add(s)
        db.add(LoyaltyTransaction(customer_id=cid, points=5, reason="Compra"))
        db.add(Order(number=1, source="online", status="delivered", channel="delivery", customer_id=cid,
                     customer_name="Marta Gómez", customer_phone="11 4444-7777", address="Calle Falsa 123",
                     invoice_request='{"cuit":"20111111112"}', client_ip="203.0.113.9", note="timbre roto",
                     total_cents=150000))
        db.commit()


def test_anonymize_wipes_person_keeps_money(seeded):
    client, h = seeded
    c = _customer(client, h)
    _sale_and_order(c["id"])
    r = client.post(f"/api/customers/{c['id']}/anonymize", json={"confirm": True, "reason": "pedido del cliente"}, headers=h)
    assert r.status_code == 200, r.text
    with SessionLocal() as db:
        cu = db.get(Customer, c["id"])
        assert cu.name == f"Cliente anonimizado #{c['id']}" and cu.anonymized_at and not cu.active
        assert not any([cu.phone, cu.email, cu.address, cu.address_ref, cu.birthday, cu.notes]) and cu.points == 0
        s = db.query(Sale).filter_by(number=9001).one()
        assert s.total_cents == 150000 and s.customer_id == c["id"] and s.notes is None
        assert s.items[0].total_cents == 150000
        o = db.query(Order).filter_by(customer_id=c["id"]).one()
        assert o.total_cents == 150000
        assert not any([o.customer_name, o.customer_phone, o.address, o.invoice_request, o.client_ip, o.note])
        assert db.query(LoyaltyTransaction).filter_by(customer_id=c["id"]).count() == 0
        dump = " ".join(str(a.payload) for a in db.query(AuditLog).all())
        assert "Marta" not in dump and "4444" not in dump and "marta@" not in dump
        assert db.query(AuditLog).filter_by(action="anonymize", entity="customer", entity_id=c["id"]).count() == 1
    assert client.post(f"/api/customers/{c['id']}/anonymize", json={"confirm": True}, headers=h).status_code == 409
    assert client.patch(f"/api/customers/{c['id']}", json={"active": True}, headers=h).status_code == 409
    assert client.get(f"/api/customers/{c['id']}/export", headers=h).status_code == 409


def test_anonymize_needs_confirm_permission_and_no_debt(seeded):
    client, h = seeded
    c = _customer(client, h)
    assert client.post(f"/api/customers/{c['id']}/anonymize", json={}, headers=h).status_code == 422
    assert client.post(f"/api/customers/{c['id']}/anonymize", json={"confirm": False}, headers=h).status_code == 422
    cajero = login(client, "Caja Demo", "1111")
    assert client.post(f"/api/customers/{c['id']}/anonymize", json={"confirm": True}, headers=cajero).status_code == 403
    assert client.get(f"/api/customers/{c['id']}/export", headers=cajero).status_code == 403
    with SessionLocal() as db:
        db.get(Customer, c["id"]).balance_cents = 5000
        db.commit()
    r = client.post(f"/api/customers/{c['id']}/anonymize", json={"confirm": True}, headers=h)
    assert r.status_code == 409 and "cuenta corriente" in r.json()["detail"]
    with SessionLocal() as db:
        assert db.get(Customer, c["id"]).name == "Marta Gómez"  # nothing was touched


def test_anonymize_scrubs_unlinked_order_with_same_phone(seeded):
    client, h = seeded
    c = _customer(client, h)
    with SessionLocal() as db:
        db.add(Order(number=2, source="online", status="rejected", channel="llevar", customer_name="Marta",
                     customer_phone="+54 9 11 4444-7777", total_cents=0))
        db.add(Order(number=3, source="online", status="rejected", channel="llevar", customer_name="Otra",
                     customer_phone="11 2222-0000", total_cents=0))
        db.commit()
    client.post(f"/api/customers/{c['id']}/anonymize", json={"confirm": True}, headers=h)
    with SessionLocal() as db:
        assert db.query(Order).filter_by(number=2).one().customer_phone is None
        assert db.query(Order).filter_by(number=3).one().customer_phone == "11 2222-0000"


def test_export_has_everything_and_is_audited(seeded):
    client, h = seeded
    c = _customer(client, h)
    _sale_and_order(c["id"])
    r = client.get(f"/api/customers/{c['id']}/export", headers=h)
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    d = r.json()
    assert d["customer"]["phone"] == "11 4444-7777" and d["customer"]["email"] == "marta@example.com"
    assert d["sales"][0]["total_cents"] == 150000 and d["sales"][0]["items"][0]["name"] == "Latte"
    assert d["online_orders"][0]["client_ip"] == "203.0.113.9" and d["online_orders"][0]["address"] == "Calle Falsa 123"
    assert d["loyalty_transactions"][0]["points"] == 5
    with SessionLocal() as db:
        assert db.query(AuditLog).filter_by(action="export", entity="customer", entity_id=c["id"]).count() == 1


def test_retention_blanks_only_old_finished_online_orders(seeded):
    old = utcnow() - timedelta(days=200)
    with SessionLocal() as db:
        def mk(n, status, created, source="online"):
            db.add(Order(number=n, source=source, status=status, channel="llevar", customer_name="Ana",
                         customer_phone="11 1", address="X 1", client_ip="1.2.3.4", total_cents=1000, created_at=created))
        mk(10, "delivered", old)
        mk(11, "delivered", utcnow())  # recent: kept
        mk(12, "preparing", old)  # still active: kept
        mk(13, "delivered", old, source="pos")  # not online: contact kept, but its IP goes
        db.commit()
        assert privacy.purge_online_order_contacts(db) == 1
        by = {o.number: o for o in db.query(Order).all()}
        assert by[10].customer_name is None and by[10].client_ip is None and by[10].total_cents == 1000
        assert by[11].customer_name == "Ana" and by[12].customer_name == "Ana" and by[13].customer_name == "Ana"
        assert by[13].client_ip is None and by[11].client_ip == "1.2.3.4" and by[12].client_ip is None
        assert db.query(AuditLog).filter_by(action="retention_purge").count() == 1


def test_retention_is_configurable_and_can_be_off(seeded):
    from app.services import settings as settings_svc

    with SessionLocal() as db:
        db.add(Order(number=20, source="online", status="cancelled", channel="llevar", customer_name="Ana",
                     total_cents=0, created_at=utcnow() - timedelta(days=40)))
        db.commit()
        assert privacy.retention_days(db) == 90
        assert privacy.purge_online_order_contacts(db) == 0  # 40 d < 90 d
        settings_svc.put(db, "privacy", {"online_order_contact_days": 30})
        db.commit()
        assert privacy.purge_online_order_contacts(db) == 1
        db.add(Order(number=21, source="online", status="cancelled", channel="llevar", customer_name="Ana",
                     total_cents=0, created_at=utcnow() - timedelta(days=999)))
        settings_svc.put(db, "privacy", {"online_order_contact_days": 0})  # 0 = never
        db.commit()
        assert privacy.purge_online_order_contacts(db) == 0
