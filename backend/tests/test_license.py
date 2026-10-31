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
