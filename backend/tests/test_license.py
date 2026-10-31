import base64
import json
import time

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.licensing import status as lic_status
from app.licensing import token as lic_token
from app.licensing.machine import machine_id

DAY = 86_400


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


@pytest.fixture()
def signer():
    key = Ed25519PrivateKey.generate()
    lic_token.set_public_key(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
    lic_status.state_path().unlink(missing_ok=True)
    lic_status.store_token(None)

    def sign(**overrides) -> str:
        payload = {
            "v": 1, "lid": "L-1", "cust": "Café Test", "plan": "pro", "features": ["*"],
            "mid": machine_id(), "iat": int(time.time()), "exp": int(time.time()) + 30 * DAY, "grace": 10,
        } | overrides
        body = _b64(json.dumps(payload).encode())
        return f"BLOOM1.{body}.{_b64(key.sign(f'BLOOM1.{body}'.encode()))}"

    yield sign
    lic_token.set_public_key(None)
    lic_status.store_token(None)
    lic_status.state_path().unlink(missing_ok=True)


def test_no_license_is_free():
    s = lic_status.evaluate(None)
    assert s.plan == "free" and not s.valid and not s.has("reports")


def test_valid_subscription(signer):
    s = lic_status.evaluate(signer())
    assert s.valid and s.plan == "pro" and s.has("reports") and not s.in_grace
    assert s.days_left == 30


def test_feature_subset(signer):
    s = lic_status.evaluate(signer(features=["barista"]))
    assert s.has("barista") and not s.has("reports")


def test_perpetual(signer):
    s = lic_status.evaluate(signer(exp=None, grace=0))
    assert s.valid and s.perpetual and s.expires_at is None


def test_grace_period_then_expired(signer):
    now = time.time()
    in_grace = lic_status.evaluate(signer(exp=int(now) - 3 * DAY), now)
    assert in_grace.valid and in_grace.in_grace and in_grace.days_left == 7
    expired = lic_status.evaluate(signer(exp=int(now) - 11 * DAY), now)
    assert not expired.valid and expired.plan == "free" and "venció" in expired.problem


def test_trial_has_no_grace(signer):
    s = lic_status.evaluate(signer(plan="trial", exp=int(time.time()) - 60, grace=0))
    assert not s.valid and "prueba" in s.problem


def test_other_machine_rejected(signer):
    s = lic_status.evaluate(signer(mid="0" * 32))
    assert not s.valid and "otra computadora" in s.problem


def test_tampered_token_rejected(signer):
    token = signer(features=["barista"])
    prefix, body, sig = token.split(".")
    forged = json.loads(base64.urlsafe_b64decode(body + "=="))
    forged["features"] = ["*"]
    bad = f"{prefix}.{_b64(json.dumps(forged).encode())}.{sig}"
    s = lic_status.evaluate(bad)
    assert not s.valid and "firma" in s.problem


def test_token_from_another_vendor_key_rejected(signer):
    other = Ed25519PrivateKey.generate()
    body = _b64(json.dumps({"v": 1, "mid": machine_id(), "plan": "pro", "features": ["*"], "exp": None}).encode())
    s = lic_status.evaluate(f"BLOOM1.{body}.{_b64(other.sign(f'BLOOM1.{body}'.encode()))}")
    assert not s.valid


def test_clock_rollback_detected(signer):
    token = signer()
    lic_status.write_state(max_seen=time.time())
    s = lic_status.evaluate(token, time.time() - 2 * DAY)
    assert not s.valid and "fecha" in s.problem


def test_api_status_import_and_gating(seeded, signer):
    client, h = seeded
    r = client.get("/api/license", headers=h).json()
    assert r["plan"] == "free" and "reports" in r["catalog"]
    # Pro capabilities answer 402 on Free
    assert client.put("/api/settings/network", json={"lan_enabled": True}, headers=h).status_code == 402
    bad = client.post("/api/license/import", json={"token": signer(mid="1" * 32)}, headers=h)
    assert bad.status_code == 400
    ok = client.post("/api/license/import", json={"token": signer()}, headers=h)
    assert ok.status_code == 200 and ok.json()["valid"]
    assert client.put("/api/settings/network", json={"lan_enabled": True}, headers=h).status_code == 200


def test_only_admin_manages_license(seeded, signer):
    from tests.conftest import login

    client, _ = seeded
    hc = login(client, "Caja Demo", "1111")
    assert client.get("/api/license", headers=hc).status_code == 200
    assert client.post("/api/license/import", json={"token": signer()}, headers=hc).status_code == 403


def test_free_plan_limits(seeded):
    from app.licensing import status

    client, h = seeded
    status.store_token(None)  # Free
    # Demo data already has more than 2 users: creating another needs Pro
    r = client.post("/api/users", json={"name": "Nuevo", "pin": "4321", "role": "cajero", "color": "blue"}, headers=h)
    assert r.status_code == 402
    assert client.put("/api/settings/network", json={"lan_enabled": True}, headers=h).status_code == 402
    assert client.put("/api/settings/network", json={"lan_enabled": False}, headers=h).status_code == 200
    # Core keeps working on Free
    assert client.get("/api/dashboard", headers=h).status_code == 200
    assert client.get("/api/pos/catalog", headers=h).status_code == 200


def test_subscription_checkout_activates_when_paid(seeded, signer, monkeypatch):
    """The app side of Mercado Pago billing, with the license server simulated."""
    from app.licensing import client as lc

    client, h = seeded
    state = {"status": "pending"}
    calls = []

    def fake_post(path, body):
        calls.append((path, body))
        return {"checkout_id": "co-1", "url": "https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_id=x"}

    def fake_get(path, query=None):
        if path == "/v1/plans":
            return {"currency": "ARS", "enabled": True, "plans": {"pro_mensual": {"label": "Pro mensual", "amount_cents": 1500000}}}
        resp = {"status": state["status"], "plan": "pro_mensual"}
        if state["status"] == "authorized":
            resp |= {"key": "BLOOM-AAAAA-BBBBB-CCCCC-DDDDD", "token": signer()}
        return resp

    monkeypatch.setattr(lc, "_post", fake_post)
    monkeypatch.setattr(lc, "_get", fake_get)

    assert client.get("/api/license/plans", headers=h).json()["plans"]["pro_mensual"]["amount_cents"] == 1500000
    r = client.post("/api/license/checkout", json={"plan": "pro_mensual", "email": "dueno@example.com"}, headers=h)
    assert r.status_code == 200 and r.json()["url"].startswith("https://www.mercadopago.com.ar/")
    assert calls[0][1]["email"] == "dueno@example.com" and calls[0][1]["machine_id"]
    assert client.get("/api/license/checkout/co-1", headers=h).json()["status"] == "pending"
    assert not client.get("/api/license", headers=h).json()["valid"]

    state["status"] = "authorized"
    r = client.get("/api/license/checkout/co-1", headers=h).json()
    assert r["status"] == "authorized" and r["license"]["valid"] and r["key"].startswith("BLOOM-")
    assert {"catalog", "pro_label", "pending_checkout"} <= r["license"].keys()  # full shape, like GET /license
    assert client.get("/api/license", headers=h).json()["valid"]
    # Bad email never reaches the server
    assert client.post("/api/license/checkout", json={"plan": "pro_mensual", "email": "nope"}, headers=h).status_code == 422


def test_pending_checkout_activates_in_background(seeded, signer, monkeypatch):
    """Paid while the app was closed (or the dialog dismissed): the background job finishes it."""
    from app.licensing import client as lc
    from app.licensing import status as st

    client, h = seeded
    st.write_state(pending_checkout=None)
    paid = {"done": False}
    monkeypatch.setattr(lc, "server_url", lambda: "https://licencias.example.com")
    monkeypatch.setattr(lc, "_post", lambda path, body: {"checkout_id": "co-9", "url": "https://mp.example/x"})

    def fake_get(path, query=None):
        if not paid["done"]:
            return {"status": "pending", "plan": "pro_mensual"}
        return {"status": "authorized", "plan": "pro_mensual", "key": "BLOOM-K", "token": signer()}

    monkeypatch.setattr(lc, "_get", fake_get)
    client.post("/api/license/checkout", json={"plan": "pro_mensual", "email": "a@example.com"}, headers=h)
    assert client.get("/api/license", headers=h).json()["pending_checkout"] == "co-9"
    lc.check_pending_checkout()
    assert not st.current_status(force=True).valid  # not paid yet
    paid["done"] = True
    lc.check_pending_checkout()
    assert st.current_status(force=True).valid
    assert client.get("/api/license", headers=h).json()["pending_checkout"] is None


def test_bad_token_from_server_never_replaces_a_working_license(seeded, signer, monkeypatch):
    from app.licensing import client as lc
    from app.licensing import status as st

    st.store_token(signer())
    monkeypatch.setattr(lc, "_post", lambda path, body: {"token": "BLOOM1.bad.token"})
    with pytest.raises(lc.LicenseServerError):
        lc.activate("BLOOM-XXXXX")
    assert st.current_status(force=True).valid
