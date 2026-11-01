"""Accepting a subscription price change from the app (the server is mocked at `_post`)."""

from app.licensing import client as lc
from app.licensing import status as lic_status
from app.models import AuditLog

CHANGE = {"old_amount_cents": 1_000_000, "new_amount_cents": 1_250_000, "effective_at": "2026-12-01T00:00:00",
          "accepted": False, "needs_acceptance": True}


def _sub(**change):
    return {"has_subscription": True, "status": "authorized", "plan": "pro_mensual", "plan_label": "Pro mensual",
            "amount_cents": 1_000_000, "days": 30, "paid_through": "2026-11-20T00:00:00",
            "cancellation_code": None, "pending_price_change": {**CHANGE, **change}}


def test_accept_price_is_admin_only_audited_and_cached(seeded, monkeypatch):
    client, h = seeded
    calls = []

    def fake_post(path, body):
        calls.append((path, body))
        return _sub(accepted=path.endswith("accept-price"))

    monkeypatch.setattr(lc, "_post", fake_post)
    lic_status.write_state(subscription=None)

    # The status is remembered: GET /api/license shows the pending change without going online
    assert client.get("/api/license/subscription", headers=h).json()["pending_price_change"]["accepted"] is False
    info = client.get("/api/license", headers=h).json()
    assert info["pending_price_change"]["new_amount_cents"] == 1_250_000

    r = client.post("/api/license/subscription/accept-price", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["pending_price_change"]["accepted"] is True
    assert calls[-1][0] == "/v1/subscription/accept-price" and "token" in calls[-1][1]
    assert client.get("/api/license", headers=h).json()["pending_price_change"]["accepted"] is True
    with client_db() as db:
        row = db.query(AuditLog).filter_by(action="accept_price").one()
        assert row.payload["new_amount_cents"] == 1_250_000


def test_cashier_cannot_accept(seeded, monkeypatch):
    client, _ = seeded
    from tests.conftest import login

    monkeypatch.setattr(lc, "_post", lambda path, body: _sub())
    cashier = login(client, "Caja Demo", "1111")
    assert client.post("/api/license/subscription/accept-price", headers=cashier).status_code == 403


def test_server_error_is_reported(seeded, monkeypatch):
    client, h = seeded

    def boom(path, body):
        raise lc.LicenseServerError("No hay ningún cambio de precio pendiente.")

    monkeypatch.setattr(lc, "_post", boom)
    r = client.post("/api/license/subscription/accept-price", headers=h)
    assert r.status_code == 400 and "pendiente" in r.json()["detail"]


def test_cancelled_subscription_hides_the_banner():
    lic_status.write_state(subscription={"at": 0, "data": {**_sub(), "status": "cancelled"}})
    assert lc.pending_price_change() is None
    lic_status.write_state(subscription=None)
    assert lc.pending_price_change() is None


def client_db():
    from app.db import SessionLocal

    return SessionLocal()
