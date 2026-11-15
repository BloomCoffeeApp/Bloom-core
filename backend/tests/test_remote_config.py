"""Signed remote config: verification, replay/expiry rules, offline cache, its uses in the app."""

import base64
import json
import time

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app import config, remote_config
from app.licensing import client as lc
from app.licensing import status as lic_status
from app.licensing import token as lic_token
from app.services import updates

KEY = Ed25519PrivateKey.generate()
OTHER = Ed25519PrivateKey.generate()


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def envelope(key=KEY, **overrides) -> dict:
    now = int(time.time())
    payload = {
        "v": 1, "iat": now, "exp": now + 7 * 86_400,
        "updates": {"manifest_url": "https://updates.example.com/latest.json", "min_version": None,
                    "release_notes_url": "https://example.com/novedades"},
        "support": {"email": "soporte@example.com", "whatsapp": "+54 9 11 0000-0000",
                    "terms_url": "https://example.com/terminos", "privacy_url": "http://inseguro.example.com"},
        "announcements": [],
    } | overrides
    return {"payload": payload, "signature": b64(key.sign(remote_config.canonical_message(payload)))}


@pytest.fixture(autouse=True)
def vendor_key(monkeypatch):
    lic_token.set_public_key(KEY.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
    remote_config.cache_path().unlink(missing_ok=True)
    remote_config.reset()
    monkeypatch.delenv("BLOOM_UPDATE_MANIFEST", raising=False)
    monkeypatch.setattr(lc, "server_url", lambda: "https://licencias.example.com")
    yield
    remote_config.cache_path().unlink(missing_ok=True)
    remote_config.reset()


def serve(monkeypatch, env):
    calls = []

    def fake_get(path, query=None):
        calls.append(path)
        return env

    monkeypatch.setattr(lc, "_get", fake_get)
    return calls


def test_valid_config_is_cached_and_used(monkeypatch):
    calls = serve(monkeypatch, envelope())
    assert remote_config.fetch()["v"] == 1
    assert calls == ["/v1/config"]
    assert remote_config.manifest_url() == "https://updates.example.com/latest.json"
    assert updates.manifest_url() == "https://updates.example.com/latest.json"  # config wins over brand.json
    s = remote_config.support()
    assert s["email"] == "soporte@example.com" and s["terms_url"].startswith("https://")
    assert s["privacy_url"] is None  # only https links are shown
    # Offline later: the cached copy is still used after a restart
    remote_config.reset()
    assert remote_config.manifest_url() == "https://updates.example.com/latest.json"


def test_tampered_or_foreign_config_rejected(monkeypatch):
    env = envelope()
    env["payload"]["updates"]["manifest_url"] = "https://evil.example.com/latest.json"
    serve(monkeypatch, env)
    with pytest.raises(remote_config.ConfigError, match="firma"):
        remote_config.fetch()
    serve(monkeypatch, envelope(key=OTHER))
    with pytest.raises(remote_config.ConfigError, match="firma"):
        remote_config.fetch()
    serve(monkeypatch, {"payload": envelope()["payload"]})
    with pytest.raises(remote_config.ConfigError):
        remote_config.fetch()
    assert remote_config.current() is None


def test_license_token_signature_is_not_a_config():
    """Domain separation: a valid license-style signature over the same JSON doesn't verify."""
    payload = envelope()["payload"]
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(remote_config.ConfigError):
        remote_config.verify({"payload": payload, "signature": b64(KEY.sign(body))})


def test_expired_future_and_replayed_configs_rejected(monkeypatch):
    now = int(time.time())
    serve(monkeypatch, envelope(iat=now - 10 * 86_400, exp=now - 3 * 86_400))
    with pytest.raises(remote_config.ConfigError, match="venció"):
        remote_config.fetch()
    serve(monkeypatch, envelope(iat=now + 3 * 86_400, exp=now + 10 * 86_400))
    with pytest.raises(remote_config.ConfigError, match="futura"):
        remote_config.fetch()
    # A newer config is cached; an older (still valid) one can't roll it back
    serve(monkeypatch, envelope(iat=now))
    remote_config.fetch()
    serve(monkeypatch, envelope(iat=now - 3600, updates={"manifest_url": "https://old.example.com/x.json"}))
    with pytest.raises(remote_config.ConfigError, match="vieja"):
        remote_config.fetch()
    assert remote_config.manifest_url() == "https://updates.example.com/latest.json"


def test_expired_cache_still_used_offline(monkeypatch):
    now = int(time.time())
    remote_config.cache_path().write_text(json.dumps(envelope(iat=now - 30 * 86_400, exp=now - 20 * 86_400)))
    assert remote_config.manifest_url() == "https://updates.example.com/latest.json"


def test_tampered_cache_is_ignored():
    env = envelope()
    env["payload"]["support"]["email"] = "otro@example.com"
    remote_config.cache_path().write_text(json.dumps(env))
    assert remote_config.current() is None and remote_config.support()["email"] is None


def test_refresh_never_raises_offline_and_backs_off(monkeypatch):
    def offline(path, query=None):
        raise lc.LicenseServerError("sin internet")

    monkeypatch.setattr(lc, "_get", offline)
    remote_config.refresh_if_due(now=1000.0)
    calls = serve(monkeypatch, envelope())
    remote_config.refresh_if_due(now=1000.0 + 60)  # retries only after 30 min
    assert calls == []
    remote_config.refresh_if_due(now=1000.0 + remote_config.RETRY_AFTER_ERROR_S + 1)
    assert calls == ["/v1/config"]


def test_no_server_configured_does_nothing(monkeypatch):
    monkeypatch.setattr(lc, "server_url", lambda: None)
    assert remote_config.fetch() is None
    assert updates.manifest_url() == (config.BRAND.get("updateManifest") or None)


def test_env_override_wins_in_development(monkeypatch):
    serve(monkeypatch, envelope())
    remote_config.fetch()
    monkeypatch.setenv("BLOOM_UPDATE_MANIFEST", "http://127.0.0.1:9/latest.json")
    assert updates.manifest_url() == "http://127.0.0.1:9/latest.json"


def test_min_version_marks_update_required(monkeypatch):
    serve(monkeypatch, envelope(updates={"manifest_url": None, "min_version": "999.0.0", "release_notes_url": None}))
    remote_config.fetch()
    st = updates.status()
    assert st["required"] and st["min_version"] == "999.0.0"
    serve(monkeypatch, envelope(iat=int(time.time()) + 1, updates={"min_version": "0.0.1"}))
    remote_config.fetch()
    assert updates.status()["required"] is False


def test_announcements_filtered_by_date_and_target(monkeypatch):
    now = time.time()
    iso = lambda t: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))  # noqa: E731
    items = [
        {"id": 1, "title": "Para todos", "body": "Hola", "level": "info", "target": "all", "starts_at": None, "ends_at": None},
        {"id": 2, "title": "Futuro", "body": "", "level": "info", "target": "all", "starts_at": iso(now + 3600), "ends_at": None},
        {"id": 3, "title": "Terminado", "body": "", "level": "info", "target": "all", "starts_at": None, "ends_at": iso(now - 60)},
        {"id": 4, "title": "Solo gratis", "body": "", "level": "warning", "target": "free", "starts_at": None, "ends_at": None},
        {"id": 5, "title": "Mensual", "body": "", "level": "critical", "target": "plan:pro_mensual", "starts_at": None, "ends_at": None},
        {"id": 6, "title": "Nivel raro", "body": "", "level": "<b>", "target": "pro", "starts_at": None, "ends_at": None},
    ]
    serve(monkeypatch, envelope(announcements=items))
    remote_config.fetch()
    pro = lic_status.LicenseStatus(plan="pro", valid=True, plan_key="pro_mensual")
    assert [a["id"] for a in remote_config.announcements(pro, now)] == [1, 5, 6]
    assert remote_config.announcements(pro, now)[2]["level"] == "info"
    free = lic_status.LicenseStatus()
    assert [a["id"] for a in remote_config.announcements(free, now)] == [1, 4]
    assert [a["id"] for a in remote_config.announcements(free, now + 7200)] == [1, 2, 4]


def test_endpoint_for_the_ui(seeded, monkeypatch):
    client, h = seeded
    assert client.get("/api/remote-config").status_code == 401
    empty = client.get("/api/remote-config", headers=h).json()
    assert empty["announcements"] == [] and empty["support"]["email"] is None and empty["required"] is False
    serve(monkeypatch, envelope(announcements=[
        {"id": 7, "title": "Mantenimiento", "body": "El domingo", "level": "warning", "target": "all",
         "starts_at": None, "ends_at": None}]))
    remote_config.fetch()
    body = client.get("/api/remote-config", headers=h).json()
    assert body["announcements"][0]["title"] == "Mantenimiento"
    assert body["support"]["whatsapp"] == "+54 9 11 0000-0000"
    assert body["release_notes_url"] == "https://example.com/novedades"


def test_signed_holidays_are_read_per_country_and_year_and_never_raise(monkeypatch):
    rows = [{"date": "2026-11-27", "name": "Día decretado", "kind": "national"}, "basura", 7]
    serve(monkeypatch, envelope(holidays={"AR": {"2026": rows, "2027": "no es una lista"}, "uy": {"2026": []}}))
    assert remote_config.holidays("AR", 2026) is None  # nothing fetched yet
    assert remote_config.fetch()["holidays"]["AR"]["2026"] == rows
    assert remote_config.holidays("AR", 2026) == [rows[0]]  # only the dict entries survive
    assert remote_config.holidays("ar", 2026) == [rows[0]]  # the country code is case-insensitive
    assert remote_config.holidays("AR", 2027) is None  # malformed year list: ignored
    assert remote_config.holidays("AR", 2030) is None  # the vendor published nothing for that year
    assert remote_config.holidays("CL", 2026) is None
