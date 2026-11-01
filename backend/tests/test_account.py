"""Optional vendor account (link with email → code) and email preferences; the server is mocked at
`_post` / `_put` of app.licensing.client."""

from app.licensing import client as lc
from app.licensing import status as lic_status
from app.models import AuditLog
from tests.conftest import login

PREFS = {"email": "dueno@example.com", "business_name": "Café Test",
         "preferences": {"news": False, "updates": True, "transactional": True},
         "categories": [{"key": "news", "label": "Novedades y promociones", "description": "", "locked": False},
                        {"key": "transactional", "label": "Cobros", "description": "", "locked": True}]}


def _server(monkeypatch, url="https://licencias.example"):
    monkeypatch.setenv("BLOOM_LICENSE_SERVER", url)
    lic_status.write_state(account=None)


def test_link_flow_stores_account_and_audits(seeded, monkeypatch):
    client, h = seeded
    _server(monkeypatch)
    calls = []

    def fake_post(path, body):
        calls.append((path, body))
        if path == "/v1/account/link/start":
            return {"ok": True, "message": "Te mandamos un código", "expires_in": 900}
        if path == "/v1/account/link/confirm":
            return {"account_token": "BLOOMACCT1.x.y", "account": {"email": "dueno@example.com", "business_name": "Café Test"},
                    "trial_status": "has_license", "trial_token": None}
        if path == "/v1/account/unlink":
            return {"ok": True}
        raise AssertionError(path)

    monkeypatch.setattr(lc, "_post", fake_post)
    assert client.get("/api/account", headers=h).json()["linked"] is False
    r = client.post("/api/account/link/start", json={"email": "Dueno@Example.com", "accept_terms": True,
                                                     "marketing_opt_in": True}, headers=h)
    assert r.status_code == 200, r.text
    body = calls[0][1]
    assert body["machine_id"] and body["business_name"] == "Café Test" and body["marketing_opt_in"] is True
    r = client.post("/api/account/link/confirm", json={"email": "dueno@example.com", "code": "123456"}, headers=h)
    assert r.status_code == 200 and r.json()["linked"] and r.json()["account"]["email"] == "dueno@example.com"
    assert "token" not in r.json()["account"]  # the token never goes to the UI
    assert lic_status.read_state()["account"]["token"] == "BLOOMACCT1.x.y"
    with client_db() as db:
        assert db.query(AuditLog).filter_by(action="link", entity="account").count() == 1
    # Unlink forgets it locally (even if the server didn't answer)
    assert client.delete("/api/account", headers=h).json()["linked"] is False
    assert calls[-1][0] == "/v1/account/unlink" and lic_status.read_state()["account"] is None


def test_link_requires_terms_and_valid_input(seeded, monkeypatch):
    client, h = seeded
    _server(monkeypatch)
    monkeypatch.setattr(lc, "_post", lambda path, body: {"ok": True})
    assert client.post("/api/account/link/start", json={"email": "a@b.co"}, headers=h).status_code == 400
    assert client.post("/api/account/link/start", json={"email": "nope", "accept_terms": True}, headers=h).status_code == 422
    assert client.post("/api/account/link/confirm", json={"email": "a@b.co", "code": "12"}, headers=h).status_code == 422


def test_wrong_code_reports_server_message(seeded, monkeypatch):
    client, h = seeded
    _server(monkeypatch)

    def boom(path, body):
        raise lc.LicenseServerError("El código es incorrecto o venció.")

    monkeypatch.setattr(lc, "_post", boom)
    r = client.post("/api/account/link/confirm", json={"email": "a@b.co", "code": "123456"}, headers=h)
    assert r.status_code == 400 and "incorrecto" in r.json()["detail"]
    assert client.get("/api/account", headers=h).json()["linked"] is False


def test_link_applies_trial_only_on_free(seeded, monkeypatch, tmp_path):
    client, h = seeded
    _server(monkeypatch)
    accepted = []
    monkeypatch.setattr(lc, "_accept", lambda resp: accepted.append(resp["token"]))
    monkeypatch.setattr(lc, "_post", lambda path, body: {
        "account_token": "BLOOMACCT1.a.b", "account": {"email": "x@y.co"}, "trial_status": "started",
        "trial_token": "BLOOM1.trial.sig"})
    # The suite runs with a valid Pro license: the trial token is NOT applied
    r = client.post("/api/account/link/confirm", json={"email": "x@y.co", "code": "123456"}, headers=h).json()
    assert r["trial_status"] == "started" and r["trial_started"] is False and accepted == []
    lic_status.store_token(None)  # free plan now
    r = client.post("/api/account/link/confirm", json={"email": "x@y.co", "code": "123456"}, headers=h).json()
    assert r["trial_started"] is True and accepted == ["BLOOM1.trial.sig"]


def test_preferences_proxy_with_account_or_license_token(seeded, monkeypatch):
    client, h = seeded
    _server(monkeypatch)
    calls = []
    monkeypatch.setattr(lc, "_post", lambda path, body: calls.append(("POST", path, body)) or PREFS)
    monkeypatch.setattr(lc, "_put", lambda path, body: calls.append(("PUT", path, body)) or
                        {**PREFS, "preferences": {**PREFS["preferences"], "news": body["news"]}})
    r = client.get("/api/account/preferences", headers=h).json()
    assert r["available"] and r["preferences"]["updates"] is True
    assert calls[-1][2]["token"].startswith("BLOOM1.")  # not linked: the license token identifies the customer
    lic_status.write_state(account={"token": "BLOOMACCT1.q.w", "email": "dueno@example.com"})
    r = client.put("/api/account/preferences", json={"news": True}, headers=h)
    assert r.status_code == 200 and r.json()["preferences"]["news"] is True
    assert calls[-1][:2] == ("PUT", "/v1/account/preferences") and calls[-1][2]["token"] == "BLOOMACCT1.q.w"
    with client_db() as db:
        assert db.query(AuditLog).filter_by(entity="email_preferences").count() == 1


def test_preferences_unavailable_offline_or_without_server(seeded, monkeypatch):
    client, h = seeded
    monkeypatch.delenv("BLOOM_LICENSE_SERVER", raising=False)
    monkeypatch.setattr(lc, "server_url", lambda: None)
    r = client.get("/api/account/preferences", headers=h).json()
    assert r["available"] is False and "servidor" in r["reason"]
    monkeypatch.setattr(lc, "server_url", lambda: "https://licencias.example")

    def offline(path, body):
        raise lc.LicenseServerError("No se pudo conectar con el servidor de licencias.")

    monkeypatch.setattr(lc, "_post", offline)
    r = client.get("/api/account/preferences", headers=h).json()
    assert r["available"] is False and "conectar" in r["reason"]
    monkeypatch.setattr(lc, "_put", offline)
    assert client.put("/api/account/preferences", json={"news": True}, headers=h).status_code == 400


def test_account_is_admin_only(seeded):
    client, _ = seeded
    cashier = login(client, "Caja Demo", "1111")
    assert client.get("/api/account", headers=cashier).status_code == 403
    assert client.get("/api/account/preferences", headers=cashier).status_code == 403


def client_db():
    from app.db import SessionLocal

    return SessionLocal()
