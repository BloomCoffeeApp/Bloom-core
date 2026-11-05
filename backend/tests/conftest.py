import os
import sqlite3
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="cafe-test-"))
os.environ["CAFE_DATA_DIR"] = str(_tmp)
os.environ["CAFE_DB_PATH"] = str(_tmp / "test.db")
os.environ.pop("BLOOM_LICENSE_SERVER", None)

import pytest  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import SessionLocal, engine  # noqa: E402
from app.main import bloom_pro  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base  # noqa: E402


# The suite exercises the Pro edition: every test gets a valid Pro license signed with a
# throwaway key (test_license.py swaps in its own signer to test Free and edge cases).
_TEST_KEY = Ed25519PrivateKey.generate()


def pro_token(**overrides) -> str:
    import base64
    import json
    import time

    from app.licensing.machine import machine_id

    b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()  # noqa: E731
    payload = {"v": 1, "lid": "L-test", "cust": "Tests", "plan": "pro", "features": ["*"],
               "mid": machine_id(), "iat": int(time.time()), "exp": None, "grace": 0} | overrides
    body = b64(json.dumps(payload).encode())
    return f"BLOOM1.{body}.{b64(_TEST_KEY.sign(f'BLOOM1.{body}'.encode()))}"


@pytest.fixture(autouse=True)
def pro_license():
    from app.licensing import status, token

    raw = _TEST_KEY.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    token.set_public_key(raw)
    if bloom_pro:
        from bloom_pro import _guard

        _guard.set_public_key(raw)
    status.state_path().unlink(missing_ok=True)
    status.store_token(pro_token())
    yield
    token.set_public_key(None)
    if bloom_pro:
        _guard.set_public_key(None)


@pytest.fixture()
def db():
    from app.services import free_plan

    free_plan.invalidate()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture()
def client(db):
    from app.auth import login_throttle

    login_throttle.reset()
    return TestClient(create_app(run_lifespan=False))


_TEMPLATE = _tmp / "seeded-template.db"
_DB = Path(os.environ["CAFE_DB_PATH"])


def _sqlite_copy(src: Path, dst: Path) -> None:
    s, d = sqlite3.connect(src), sqlite3.connect(dst)
    try:
        with d:
            s.backup(d)
    finally:
        s.close()
        d.close()


@pytest.fixture()
def seeded(client):
    """First-time setup with demo data. Returns (client, admin auth headers).

    The demo seed (incl. 90 days of sales) is generated once per test run and
    restored into a fresh DB for every test, which keeps the suite fast.
    """
    if not _TEMPLATE.exists():
        r = client.post(
            "/api/setup",
            json={"business_name": "Café Test", "admin_name": "Admin", "admin_pin": "0000", "load_demo": True},
        )
        assert r.status_code == 200, r.text
        engine.dispose()
        _sqlite_copy(_DB, _TEMPLATE)
    else:
        engine.dispose()
        _sqlite_copy(_TEMPLATE, _DB)
    from app.services import free_plan

    free_plan.invalidate()
    return client, login(client, "Admin", "0000")


def login(client, name: str, pin: str) -> dict[str, str]:
    users = client.get("/api/auth/users").json()
    uid = next(u["id"] for u in users if u["name"] == name)
    r = client.post("/api/auth/login", json={"user_id": uid, "pin": pin})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}
