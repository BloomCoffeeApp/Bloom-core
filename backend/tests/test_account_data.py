"""Data rights over what the license server keeps (export / delete the account), proxied by the app.
The server is mocked at `_post` of app.licensing.client."""

from app.licensing import client as lc
from app.licensing import status as lic_status
from app.models import AuditLog
from tests.conftest import login


def _server(monkeypatch):
    monkeypatch.setenv("BLOOM_LICENSE_SERVER", "https://licencias.example")
    lic_status.write_state(account={"token": "BLOOMACCT1.a.b", "email": "dueno@example.com"})


def _audits(action: str, entity: str) -> int:
    from app.db import SessionLocal

    with SessionLocal() as db:
        return db.query(AuditLog).filter_by(action=action, entity=entity).count()


def test_export_proxies_with_account_token_and_audits(seeded, monkeypatch):
    client, h = seeded
    _server(monkeypatch)
    calls = []
    monkeypatch.setattr(lc, "_post", lambda path, body: calls.append((path, body)) or
                        {"customer": {"email": "dueno@example.com"}, "licenses": []})
    r = client.post("/api/account/data/export", headers=h)
    assert r.status_code == 200 and r.json()["customer"]["email"] == "dueno@example.com"
    assert calls == [("/v1/account/data/export", {"token": "BLOOMACCT1.a.b", "machine_id": calls[0][1]["machine_id"]})]
    assert _audits("export", "account_data") == 1


def test_delete_flow_forgets_the_link(seeded, monkeypatch):
    client, h = seeded
    _server(monkeypatch)
    calls = []

    def fake_post(path, body):
        calls.append((path, body))
        if path.endswith("/start"):
            return {"ok": True, "email": "du…@example.com", "expires_in": 900}
        return {"ok": True, "deleted": True, "retained": ["Cobros anonimizados"]}

    monkeypatch.setattr(lc, "_post", fake_post)
    r = client.post("/api/account/delete/start", headers=h)
    assert r.status_code == 200 and r.json()["email"] == "du…@example.com"
    assert client.post("/api/account/delete/confirm", json={"code": "12"}, headers=h).status_code == 422
    r = client.post("/api/account/delete/confirm", json={"code": "123456"}, headers=h)
    assert r.status_code == 200 and r.json()["deleted"] is True and r.json()["linked"] is False
    assert calls[-1] == ("/v1/account/data/delete/confirm",
                         {"token": "BLOOMACCT1.a.b", "machine_id": calls[-1][1]["machine_id"], "code": "123456"})
    assert lic_status.read_state()["account"] is None
    assert _audits("delete", "account") == 1


def test_server_errors_are_shown_and_link_is_kept(seeded, monkeypatch):
    client, h = seeded
    _server(monkeypatch)

    def refuse(path, body):
        raise lc.LicenseServerError("Tenés una suscripción activa. Cancelala primero")

    monkeypatch.setattr(lc, "_post", refuse)
    r = client.post("/api/account/delete/start", headers=h)
    assert r.status_code == 400 and "Cancelala primero" in r.json()["detail"]
    r = client.post("/api/account/delete/confirm", json={"code": "123456"}, headers=h)
    assert r.status_code == 400 and lic_status.read_state()["account"]["token"] == "BLOOMACCT1.a.b"


def test_without_server_or_account(seeded, monkeypatch):
    client, h = seeded
    monkeypatch.setattr(lc, "server_url", lambda: None)
    lic_status.write_state(account=None)
    r = client.post("/api/account/data/export", headers=h)
    assert r.status_code == 400


def test_data_rights_are_admin_only(seeded):
    client, _ = seeded
    cashier = login(client, "Caja Demo", "1111")
    assert client.post("/api/account/data/export", headers=cashier).status_code == 403
    assert client.post("/api/account/delete/start", headers=cashier).status_code == 403
