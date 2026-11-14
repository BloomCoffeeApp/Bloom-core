"""Support diagnostic («Enviar diagnóstico a soporte»): what is collected, that it is scrubbed, that it never
carries business data, that it fits the license server's closed schema and how network errors surface."""

import json
from datetime import datetime, timedelta
from typing import Annotated

import pytest
from pydantic import BaseModel, ConfigDict, Field

from app import config
from app.licensing import client as lc
from app.services import diagnostics as svc
from tests.conftest import login


# ---- copy of the closed schema of the license server (pro/license_server/diagnostics.py): extra="forbid"
class _S(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class _Err(_S):
    ts: Annotated[str, Field(max_length=40)] = ""
    kind: Annotated[str, Field(max_length=60)] = ""
    message: Annotated[str, Field(max_length=400)] = ""


class _Printer(_S):
    configured: bool = False
    last_ok: bool | None = None


class _Lic(_S):
    state: Annotated[str, Field(max_length=40)] = ""
    plan: Annotated[str, Field(max_length=60)] | None = None
    expires: Annotated[str, Field(max_length=40)] | None = None


class ServerDiagnostic(_S):
    os: Annotated[str, Field(max_length=80)] = ""
    app_version: Annotated[str, Field(max_length=20)] = ""
    db_ok: bool | None = None
    db_size_mb: Annotated[float, Field(ge=0, le=1_000_000)] | None = None
    last_backup_at: Annotated[str, Field(max_length=40)] | None = None
    backups: Annotated[int, Field(ge=0, le=100_000)] | None = None
    printer: _Printer | None = None
    license: _Lic | None = None
    modules: Annotated[list[Annotated[str, Field(max_length=40)]], Field(max_length=40)] = []
    errors: Annotated[list[_Err], Field(max_length=20)] = []
    uptime_hours: Annotated[float, Field(ge=0, le=1_000_000)] | None = None


def test_scrub_removes_personal_data():
    text = ("fallo para juan.perez@example.com en C:\\Users\\Juan\\AppData\\Bloom\\data.db "
            "con token=abcdef123456 y clave " + "A" * 40 + " en /home/maria/x")
    out = svc.scrub(text)
    assert "juan.perez" not in out and "example.com" not in out
    assert "Juan" not in out and "maria" not in out
    assert "abcdef123456" not in out and "A" * 32 not in out
    assert "[email]" in out and "[usuario]" in out and "[oculto]" in out
    assert len(svc.scrub("x " * 500, 50)) == 50
    assert svc.scrub(None) == ""


def test_recent_errors_last_24h_only_errors_scrubbed(tmp_path):
    now = datetime(2026, 11, 13, 12, 0, 0)
    fmt = "%Y-%m-%d %H:%M:%S"
    lines = [
        f"{(now - timedelta(hours=30)).strftime(fmt)},001 ERROR cafeteria.jobs: muy vieja",
        f"{(now - timedelta(hours=2)).strftime(fmt)},001 INFO cafeteria.jobs: solo info",
        f"{(now - timedelta(hours=2)).strftime(fmt)},002 WARNING cafeteria.jobs: solo aviso",
        f"{(now - timedelta(hours=1)).strftime(fmt)},003 ERROR cafeteria.printing: falló para ana@example.com en C:\\Users\\Ana\\x",
        "Traceback (most recent call last):",
        '  File "C:\\Users\\Ana\\x.py", line 1, in f',
        f"{(now - timedelta(minutes=5)).strftime(fmt)},004 CRITICAL cafeteria.db: base dañada",
    ]
    log = tmp_path / "app.log"
    log.write_text("\n".join(lines), encoding="utf-8")
    errs = svc.recent_errors(log, now)
    assert [e["kind"] for e in errs] == ["cafeteria.printing", "cafeteria.db"]
    assert "ana@" not in json.dumps(errs) and "Ana" not in json.dumps(errs)
    assert errs[0]["ts"].startswith("2026-11-13 11:00")


def test_recent_errors_caps_at_20_and_missing_log(tmp_path):
    now = datetime(2026, 11, 13, 12, 0, 0)
    log = tmp_path / "app.log"
    log.write_text("\n".join(f"2026-11-13 11:00:{i % 60:02d},000 ERROR a.b: e{i}" for i in range(50)), encoding="utf-8")
    errs = svc.recent_errors(log, now)
    assert len(errs) == 20 and errs[-1]["message"] == "e49"
    assert svc.recent_errors(tmp_path / "nope.log", now) == []


def test_build_matches_server_schema_and_has_no_business_data(seeded):
    client, h = seeded
    (config.DATA_DIR / "app.log").write_text(
        f"{datetime.now():%Y-%m-%d %H:%M:%S},000 ERROR cafeteria.x: error con dueno@example.com\n", encoding="utf-8")
    r = client.get("/api/diagnostics/preview", headers=h)
    assert r.status_code == 200, r.text
    diag = r.json()["diagnostic"]
    parsed = ServerDiagnostic.model_validate(diag)  # closed schema: unknown fields would fail
    assert parsed.db_ok is True and parsed.db_size_mb is not None and parsed.uptime_hours is not None
    assert parsed.app_version == config.APP_VERSION
    assert parsed.license and parsed.license.state == "active"
    assert parsed.errors and "dueno@" not in parsed.errors[0].message
    # Never sales, customers, products, prices or names:
    blob = json.dumps(r.json()).lower()
    products = client.get("/api/products", headers=h).json()
    assert products
    for p in products[:20]:
        assert p["name"].lower() not in blob
    for c in client.get("/api/customers", headers=h).json()[:20]:
        assert c["name"].lower() not in blob
    assert "café test" not in blob and "cents" not in blob


def test_not_available_without_server(seeded, monkeypatch):
    client, h = seeded
    monkeypatch.delenv("BLOOM_LICENSE_SERVER", raising=False)
    monkeypatch.setitem(config.BRAND, "licenseServer", None)
    r = client.get("/api/diagnostics/preview", headers=h).json()
    assert r["available"] is False and "servidor" in r["reason"]
    s = client.post("/api/diagnostics/send", json={"consent": True}, headers=h)
    assert s.status_code == 409


def test_send_requires_consent_and_admin(seeded, monkeypatch):
    client, h = seeded
    monkeypatch.setenv("BLOOM_LICENSE_SERVER", "https://licencias.example")
    monkeypatch.setattr(lc, "_post", lambda *a: pytest.fail("must not be called"))
    assert client.post("/api/diagnostics/send", json={}, headers=h).status_code == 400
    assert client.post("/api/diagnostics/send", json={"consent": False}, headers=h).status_code == 400
    cajero = login(client, "Caja Demo", "1111")
    assert client.get("/api/diagnostics/preview", headers=cajero).status_code == 403
    assert client.post("/api/diagnostics/send", json={"consent": True}, headers=cajero).status_code == 403


def test_send_posts_payload_with_token_and_audits(seeded, monkeypatch):
    client, h = seeded
    monkeypatch.setenv("BLOOM_LICENSE_SERVER", "https://licencias.example")
    calls = []

    def fake_post(path, body):
        calls.append((path, body))
        return {"support_code": "BLM-ABCD-2345"}

    monkeypatch.setattr(lc, "_post", fake_post)
    r = client.post("/api/diagnostics/send", json={"consent": True}, headers=h)
    assert r.status_code == 200 and r.json() == {"support_code": "BLM-ABCD-2345"}
    path, body = calls[0]
    assert path == "/v1/diagnostics" and body["consent"] is True and body["token"].startswith("BLOOM1.")
    assert set(body) == {"machine_id", "token", "consent", "diagnostic"}
    ServerDiagnostic.model_validate(body["diagnostic"])
    from app.db import SessionLocal
    from app.models import AuditLog

    with SessionLocal() as db:
        assert db.query(AuditLog).filter_by(action="send", entity="diagnostic").count() == 1


def test_send_anonymous_without_license(seeded, monkeypatch):
    client, h = seeded
    from app.licensing import status

    monkeypatch.setenv("BLOOM_LICENSE_SERVER", "https://licencias.example")
    status.store_token(None)
    calls = []
    monkeypatch.setattr(lc, "_post", lambda p, b: calls.append(b) or {"support_code": "BLM-ABCD-2345"})
    assert client.post("/api/diagnostics/send", json={"consent": True}, headers=h).status_code == 200
    assert "token" not in calls[0]
    assert client.get("/api/diagnostics/preview", headers=h).json()["includes_license"] is False


@pytest.mark.parametrize("error,status_code", [
    (lc.LicenseServerError("No se pudo conectar con el servidor de licencias. Revisá la conexión a internet."), 503),
    (lc.LicenseServerError("Ya mandaste varios diagnósticos. Probá de nuevo más tarde.", 429), 429),
    (lc.LicenseServerError("El servidor de licencias respondió 500.", 500), 400),
])
def test_send_maps_network_and_limit_errors(seeded, monkeypatch, error, status_code):
    client, h = seeded
    monkeypatch.setenv("BLOOM_LICENSE_SERVER", "https://licencias.example")

    def boom(*_a):
        raise error

    monkeypatch.setattr(lc, "_post", boom)
    r = client.post("/api/diagnostics/send", json={"consent": True}, headers=h)
    assert r.status_code == status_code and r.json()["detail"] == str(error)
