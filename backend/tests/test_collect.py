"""Collecting payments (Pro `payments`): provider abstraction, POS charges approved by polling, transfer
confirmation, cancel/expiry, refunds, the internal API for other modules, customer screens and the
encryption of stored credentials."""

from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.models import CashSession, CollectCharge, Product, Sale, Setting, utcnow
from app.services import collect, secret_store
from tests.conftest import pro_token

LATTE = 340000


def _pid(db, name: str) -> int:
    return db.scalar(select(Product.id).where(Product.name == name))


def _sale(db, method: str, amount: int = LATTE, **kw) -> dict:
    return {"items": [{"product_id": _pid(db, "Latte"), "qty": 1}], "channel": "salon",
            "payments": [{"method": method, "amount_cents": amount}], **kw}


def _enable_fake(client, h, **extra):
    r = client.put("/api/collect/config", json={"provider": "fake", **extra}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _sales_count(db) -> int:
    db.expire_all()
    return db.scalar(select(func.count(Sale.id)))


@pytest.fixture()
def fake(seeded):
    client, h = seeded
    _enable_fake(client, h)
    return client, h


# ---------------------------------------------------------------- provider abstraction / configuration


def test_connecting_a_provider_turns_on_the_qr_method(seeded):
    client, h = seeded
    st = client.get("/api/collect/status", headers=h).json()
    assert st["licensed"] and st["provider"] is None and st["methods"] == []
    codes = {m["code"] for m in client.get("/api/payment-methods", headers=h).json()}
    assert "mp_qr" not in codes  # off until a provider is connected
    st = _enable_fake(client, h)
    assert st["connected"] and st["methods"] == ["mp_qr"]
    codes = {m["code"] for m in client.get("/api/payment-methods", headers=h).json()}
    assert "mp_qr" in codes and "mp_point" not in codes
    # A Point device enables the Point method too.
    st = _enable_fake(client, h, point_device_id="DEV-1", point_device_name="Point mostrador")
    assert st["methods"] == ["mp_qr", "mp_point"]
    st = client.put("/api/collect/config", json={"provider": None}, headers=h).json()
    assert st["methods"] == []


def test_unknown_or_unavailable_provider(seeded, monkeypatch):
    client, h = seeded
    assert client.put("/api/collect/config", json={"provider": "getnet"}, headers=h).status_code == 400
    # The simulator is never offered in the desktop .exe.
    from app import config

    monkeypatch.setattr(config, "FROZEN", True)
    assert not collect.fake_allowed()
    assert client.put("/api/collect/config", json={"provider": "fake"}, headers=h).status_code == 400


def test_without_the_license_feature_charges_are_402(seeded, db):
    from app.licensing import status

    client, h = seeded
    _enable_fake(client, h)
    status.store_token(pro_token(features=["barista"]))
    r = client.post("/api/collect/pos-charges", json={"sale": _sale(db, "mp_qr"), "method": "mp_qr"}, headers=h)
    assert r.status_code == 402
    with pytest.raises(HTTPException) as e:
        collect.create_charge(db, kind="qr", amount_cents=100, description="x", ref="r-1")
    assert e.value.status_code == 402
    assert client.get("/api/collect/status", headers=h).json()["methods"] == []


def test_transfer_needs_alias_or_cbu(seeded):
    client, h = seeded
    r = client.put("/api/collect/config", json={"transfer": {"enabled": True}}, headers=h)
    assert r.status_code == 400
    r = client.put("/api/collect/config", json={"transfer": {"enabled": True, "alias": "cafe.ejemplo.mp"}}, headers=h)
    assert r.status_code == 200 and "transferencia" in r.json()["methods"]


# ---------------------------------------------------------------- POS: QR approved by polling -> sale paid


def test_pos_qr_charge_creates_the_sale_only_when_approved(fake, db):
    client, h = fake
    before = _sales_count(db)
    r = client.post("/api/collect/pos-charges", json={"sale": _sale(db, "mp_qr"), "method": "mp_qr"}, headers=h)
    assert r.status_code == 200, r.text
    ch = r.json()
    assert ch["status"] == "pending" and ch["kind"] == "qr" and ch["qr_data"] and ch["amount_cents"] == LATTE
    assert ch["items"][0]["name"].startswith("Latte") and ch["sale"] is None
    assert _sales_count(db) == before  # the dry run saved nothing
    # Still pending: polling keeps the sale unsaved.
    assert client.get(f"/api/collect/charges/{ch['id']}", headers=h).json()["status"] == "pending"
    # The customer pays: the next poll approves it and creates the sale in the same transaction.
    row = db.get(CollectCharge, ch["id"])
    collect.fake_set_status(row.provider_id, "approved")
    db.execute(CollectCharge.__table__.update().values(next_poll_at=utcnow() - timedelta(seconds=1)))
    db.commit()
    out = client.get(f"/api/collect/charges/{ch['id']}", headers=h).json()
    assert out["status"] == "approved" and out["sale_id"]
    assert out["sale"]["total_cents"] == LATTE and out["sale"]["payments"][0]["method"] == "mp_qr"
    assert _sales_count(db) == before + 1
    db.expire_all()
    assert db.get(CollectCharge, ch["id"]).operation_id.startswith("FAKE-")  # the provider's number, kept for the receipt
    # Polling again (or a second poller) never creates it twice.
    collect.refresh(db, db.get(CollectCharge, ch["id"]), force=True)
    assert collect.poll_due(db) == 0
    assert _sales_count(db) == before + 1


def test_background_poll_pass_approves_and_backs_off_on_errors(fake, db):
    client, h = fake
    ch = client.post("/api/collect/pos-charges", json={"sale": _sale(db, "mp_qr"), "method": "mp_qr"}, headers=h).json()
    row = db.get(CollectCharge, ch["id"])

    class Broken(collect.FakeProvider):
        def get_status(self, provider_id, kind):
            raise collect.ProviderError("sin conexión")

    collect.register_provider(collect.ProviderEntry("fake", "Fake", build=lambda _db: Broken(), connected=lambda _db: True))
    try:
        row.next_poll_at = utcnow() - timedelta(seconds=1)
        db.commit()
        assert collect.poll_due(db) == 1
        db.refresh(row)
        assert row.status == "pending" and row.poll_failures == 1
        assert row.next_poll_at > utcnow()  # backoff
    finally:
        collect.register_provider(collect.ProviderEntry(
            "fake", "Modo de prueba (simulado)", build=lambda _db: collect.FakeProvider(),
            connected=lambda _db: collect.fake_allowed()))
    collect.fake_set_status(row.provider_id, "approved")
    row.next_poll_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert collect.poll_due(db) == 0
    db.refresh(row)
    assert row.status == "approved" and row.sale_id and row.poll_failures == 0


def test_simulate_endpoint_and_rejection(fake, db):
    client, h = fake
    before = _sales_count(db)
    ch = client.post("/api/collect/pos-charges", json={"sale": _sale(db, "mp_qr"), "method": "mp_qr"}, headers=h).json()
    out = client.post(f"/api/collect/charges/{ch['id']}/simulate", json={"status": "rejected"}, headers=h).json()
    assert out["status"] == "rejected" and out["sale_id"] is None
    assert _sales_count(db) == before


def test_invalid_sale_is_rejected_before_charging(fake, db):
    client, h = fake
    # Payment doesn't match the total: the dry run fails and no charge is opened.
    r = client.post("/api/collect/pos-charges", json={"sale": _sale(db, "mp_qr", amount=1), "method": "mp_qr"}, headers=h)
    assert r.status_code == 400
    assert db.scalar(select(func.count(CollectCharge.id))) == 0


def test_cancel_and_expiry(fake, db):
    client, h = fake
    ch = client.post("/api/collect/pos-charges", json={"sale": _sale(db, "mp_qr"), "method": "mp_qr"}, headers=h).json()
    out = client.post(f"/api/collect/charges/{ch['id']}/cancel", headers=h).json()
    assert out["status"] == "cancelled"
    # A late "approval" after cancelling is ignored (the provider was told to cancel).
    row = db.get(CollectCharge, ch["id"])
    collect.fake_set_status(row.provider_id, "approved")
    assert client.get(f"/api/collect/charges/{ch['id']}", headers=h).json()["status"] == "cancelled"

    ch2 = client.post("/api/collect/pos-charges", json={"sale": _sale(db, "mp_qr"), "method": "mp_qr"}, headers=h).json()
    row2 = db.get(CollectCharge, ch2["id"])
    row2.expires_at = utcnow() - timedelta(minutes=2)
    row2.next_poll_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert client.get(f"/api/collect/charges/{ch2['id']}", headers=h).json()["status"] == "expired"


def test_cash_closed_on_approval_flags_error_and_retry_creates_the_sale(fake, db):
    client, h = fake
    ch = client.post("/api/collect/pos-charges", json={"sale": _sale(db, "mp_qr"), "method": "mp_qr"}, headers=h).json()
    session = db.scalar(select(CashSession).where(CashSession.status == "open"))
    session.status = "closed"
    db.commit()
    out = client.post(f"/api/collect/charges/{ch['id']}/simulate", json={"status": "approved"}, headers=h).json()
    assert out["status"] == "approved" and out["sale_id"] is None and "caja" in out["error"]
    session.status = "open"
    db.commit()
    out = client.post(f"/api/collect/charges/{ch['id']}/retry", headers=h).json()
    assert out["error"] is None and out["sale"]["total_cents"] == LATTE


# ---------------------------------------------------------------- transfer


def test_transfer_shown_on_screen_and_confirmed_by_the_cashier(seeded, db):
    client, h = seeded
    client.put("/api/collect/config", json={"transfer": {"enabled": True, "alias": "cafe.ejemplo.mp", "holder": "Café Ejemplo"}}, headers=h)
    screen = client.post("/api/collect/screens", json={"name": "Tablet mostrador"}, headers=h).json()
    before = _sales_count(db)
    ch = client.post("/api/collect/pos-charges",
                     json={"sale": _sale(db, "transferencia"), "method": "transferencia", "screen_id": screen["id"]},
                     headers=h).json()
    assert ch["kind"] == "transfer" and ch["provider"] == "manual"
    state = client.get(f"/api/public/customer-screen?token={screen['token']}").json()
    assert state["state"] == "pending" and state["charge"]["transfer"]["alias"] == "cafe.ejemplo.mp"
    assert state["charge"]["amount_cents"] == LATTE and state["charge"]["items"]
    # Polling never approves a transfer on its own.
    collect.refresh(db, db.get(CollectCharge, ch["id"]), force=True)
    assert _sales_count(db) == before
    out = client.post(f"/api/collect/charges/{ch['id']}/confirm", headers=h).json()
    assert out["status"] == "approved" and out["sale"]["payments"][0]["method"] == "transferencia"
    assert _sales_count(db) == before + 1
    assert client.post(f"/api/collect/charges/{ch['id']}/confirm", headers=h).status_code == 409
    assert client.get(f"/api/public/customer-screen?token={screen['token']}").json()["state"] == "approved"
    # Transfers are refunded from the bank, not from the app.
    assert client.post(f"/api/collect/sales/{out['sale_id']}/refund", json={}, headers=h).status_code == 400


# ---------------------------------------------------------------- refunds


def _paid_sale(client, h, db) -> int:
    ch = client.post("/api/collect/pos-charges", json={"sale": _sale(db, "mp_qr"), "method": "mp_qr"}, headers=h).json()
    out = client.post(f"/api/collect/charges/{ch['id']}/simulate", json={"status": "approved"}, headers=h).json()
    return out["sale_id"]


def test_partial_then_full_refund(fake, db):
    client, h = fake
    sale_id = _paid_sale(client, h, db)
    info = client.get(f"/api/collect/sales/{sale_id}", headers=h).json()
    assert info["refundable_cents"] == LATTE
    r = client.post(f"/api/collect/sales/{sale_id}/refund", json={"amount_cents": 100000, "reason": "faltó un ítem"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["refundable_cents"] == LATTE - 100000 and len(r.json()["refunds"]) == 1
    assert r.json()["charge"]["status"] == "approved"
    too_much = client.post(f"/api/collect/sales/{sale_id}/refund", json={"amount_cents": LATTE}, headers=h)
    assert too_much.status_code == 400
    r = client.post(f"/api/collect/sales/{sale_id}/refund", json={"void_sale": True}, headers=h).json()
    assert r["charge"]["status"] == "refunded" and r["refundable_cents"] == 0
    # Everything was given back and the cashier asked to void it: the sale is voided (stock back).
    assert client.get(f"/api/sales/{sale_id}", headers=h).json()["status"] == "voided"


def test_full_refund_can_void_the_sale(fake, db):
    client, h = fake
    sale_id = _paid_sale(client, h, db)
    r = client.post(f"/api/collect/sales/{sale_id}/refund", json={"void_sale": True, "reason": "error de carga"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["charge"]["status"] == "refunded"
    assert client.get(f"/api/sales/{sale_id}", headers=h).json()["status"] == "voided"


def test_refund_needs_the_void_permission(fake, db):
    from tests.conftest import login

    client, h = fake
    sale_id = _paid_sale(client, h, db)
    cashier = login(client, "Caja Demo", "1111")
    assert client.post(f"/api/collect/sales/{sale_id}/refund", json={}, headers=cashier).status_code == 403


# ---------------------------------------------------------------- internal API (other modules)


def test_internal_api_link_with_handler(seeded, db):
    client, h = seeded
    _enable_fake(client, h)
    seen: list[tuple[str, int]] = []
    collect.register_handler("test_order", on_approved=lambda _db, ch: seen.append(("ok", ch.ref_id)),
                             on_closed=lambda _db, ch: seen.append((ch.status, ch.ref_id)))
    ch = collect.create_charge(db, kind="link", amount_cents=125000, description="Pedido #23", ref="order-23",
                               ref_type="test_order", ref_id=23)
    st = collect.charge_status(db, ch.id)
    assert st["status"] == "pending" and st["url"].startswith("https://") and st["kind"] == "link"
    with pytest.raises(HTTPException):  # refs are unique
        collect.create_charge(db, kind="link", amount_cents=1, description="x", ref="order-23")
    with pytest.raises(HTTPException):  # no personal data / odd chars in the reference
        collect.create_charge(db, kind="qr", amount_cents=1, description="x", ref="juan perez@mail")
    collect.simulate(db, ch.id, "approved")
    assert seen == [("ok", 23)]
    out = collect.refund(db, ch.id, 25000)
    assert out.refunded_cents == 25000 and out.status == "approved"
    out = collect.refund(db, ch.id, None)
    assert out.status == "refunded" and out.refunded_cents == 125000
    ch2 = collect.create_charge(db, kind="qr", amount_cents=5000, description="Pedido #24", ref="order-24",
                                ref_type="test_order", ref_id=24)
    collect.cancel_charge(db, ch2.id)
    assert seen[-1] == ("cancelled", 24)


def test_unconfigured_provider_gives_a_clear_error(seeded, db):
    with pytest.raises(HTTPException) as e:
        collect.create_charge(db, kind="qr", amount_cents=100, description="x", ref="r-2")
    assert e.value.status_code == 400 and "Mercado Pago" in e.value.detail


# ---------------------------------------------------------------- customer screens


def test_customer_screen_shows_cart_qr_and_approval(fake, db):
    client, h = fake
    screen = client.post("/api/collect/screens", json={"name": "TV"}, headers=h).json()
    assert client.get("/api/public/customer-screen?token=nope").status_code == 404
    idle = client.get(f"/api/public/customer-screen?token={screen['token']}").json()
    assert idle["state"] == "idle" and idle["business_name"]
    ch = client.post("/api/collect/pos-charges",
                     json={"sale": _sale(db, "mp_qr"), "method": "mp_qr", "screen_id": screen["id"]}, headers=h).json()
    st = client.get(f"/api/public/customer-screen?token={screen['token']}").json()
    assert st["state"] == "pending" and st["charge"]["qr_png"].startswith("data:image/png;base64,")
    assert st["charge"]["items"][0]["name"].startswith("Latte") and st["charge"]["fake"] is True
    client.post(f"/api/collect/charges/{ch['id']}/simulate", json={"status": "approved"}, headers=h)
    assert client.get(f"/api/public/customer-screen?token={screen['token']}").json()["state"] == "approved"
    # Rotating the token invalidates the old link; deleting keeps the charge history.
    rotated = client.patch(f"/api/collect/screens/{screen['id']}", json={"rotate": True}, headers=h).json()
    assert client.get(f"/api/public/customer-screen?token={screen['token']}").status_code == 404
    assert client.get(f"/api/public/customer-screen?token={rotated['token']}").status_code == 200
    assert client.delete(f"/api/collect/screens/{screen['id']}", headers=h).status_code == 200
    assert db.get(CollectCharge, ch["id"]) is not None


# ---------------------------------------------------------------- encrypted credentials


def test_credentials_are_encrypted_at_rest(seeded, db):
    secret = "APP_USR-1234567890-abcdef-secret"
    collect.store_credentials(db, "mercadopago", {"access_token": secret, "user_id": 99})
    db.commit()
    db.expire_all()
    raw = db.get(Setting, collect.CREDENTIALS_SETTING).value["mercadopago"]
    assert secret not in raw and raw.split(":")[0] in ("dpapi", "fernet")
    assert collect.load_credentials(db, "mercadopago") == {"access_token": secret, "user_id": 99}
    collect.store_credentials(db, "mercadopago", None)
    db.commit()
    assert collect.load_credentials(db, "mercadopago") is None


def test_key_file_backend_roundtrip_and_tamper(tmp_path, monkeypatch):
    monkeypatch.setenv("BLOOM_SECRET_BACKEND", "file")
    monkeypatch.setenv("BLOOM_SECRET_KEY_FILE", str(tmp_path / "secret.key"))
    stored = secret_store.encrypt("token-123")
    assert stored.startswith("fernet:v1:") and "token-123" not in stored
    assert secret_store.decrypt(stored) == "token-123"
    with pytest.raises(secret_store.SecretStoreError):
        secret_store.decrypt(stored[:-4] + "AAAA")
    # Another key (e.g. a copied database on another machine) can't read it.
    (tmp_path / "secret.key").unlink()
    with pytest.raises(secret_store.SecretStoreError):
        secret_store.decrypt(stored)


@pytest.mark.skipif(__import__("sys").platform != "win32", reason="DPAPI is Windows-only")
def test_dpapi_backend_roundtrip(monkeypatch):
    monkeypatch.delenv("BLOOM_SECRET_BACKEND", raising=False)
    stored = secret_store.encrypt("ñandú-token")
    assert stored.startswith("dpapi:v1:")
    assert secret_store.decrypt(stored) == "ñandú-token"
    with pytest.raises(secret_store.SecretStoreError):
        secret_store.decrypt("dpapi:v1:" + "QUJD")
