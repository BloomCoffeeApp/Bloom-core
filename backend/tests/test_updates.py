"""In-app updates: signed manifest verification, version rules, download checks and endpoints."""

import base64
import hashlib
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app import config
from app.services import backup
from app.services import updates
from tests.conftest import login

KEY = Ed25519PrivateKey.generate()
OTHER_KEY = Ed25519PrivateKey.generate()
INSTALLER = b"MZ fake installer " * 5000


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def signed(key=KEY, **fields) -> dict:
    m = {
        "version": "99.0.0",
        "url": "https://example.com/Bloom-Setup-99.0.0.exe",
        "sha256": hashlib.sha256(INSTALLER).hexdigest(),
        "size": len(INSTALLER),
        "notes": "Mejoras y correcciones. Ñandú ☕",
        "published_at": "2026-10-01T12:00:00Z",
    } | fields
    m["signature"] = b64(key.sign(updates.canonical_message(m)))
    return m


class Server:
    """Tiny local HTTP server: path -> (status, body, headers)."""

    def __init__(self):
        self.routes: dict[str, tuple[int, bytes, dict]] = {}
        routes = self.routes

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                status, body, headers = routes.get(self.path, (404, b"not found", {}))
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def json(self, path: str, data) -> str:
        self.routes[path] = (200, json.dumps(data).encode(), {"Content-Type": "application/json"})
        return self.base + path

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture(autouse=True)
def update_env(monkeypatch, tmp_path):
    from app.licensing import token

    token.set_public_key(KEY.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
    monkeypatch.setattr(config, "APP_VERSION", "1.0.0")
    monkeypatch.setattr(updates, "download_dir", lambda: tmp_path / "dl")
    monkeypatch.setattr(updates, "EXIT_DELAY_S", 0.0)
    monkeypatch.setenv("BLOOM_UPDATE_MANIFEST", "")
    updates._reset_state()
    updates.set_exit_handler(None)
    yield
    updates._reset_state()
    updates.set_exit_handler(None)


@pytest.fixture()
def server():
    s = Server()
    yield s
    s.close()


def publish(server: Server, monkeypatch, **fields) -> dict:
    """Serves the installer + a signed manifest pointing at it; points the app at the manifest."""
    server.routes["/Bloom-Setup.exe"] = (200, INSTALLER, {"Content-Type": "application/octet-stream"})
    m = signed(url=f"{server.base}/Bloom-Setup.exe", **fields)
    monkeypatch.setenv("BLOOM_UPDATE_MANIFEST", server.json("/latest.json", m))
    return m


def wait_state(*states: str, timeout: float = 10) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = updates.status()
        if s["state"] in states:
            return s
        time.sleep(0.05)
    raise AssertionError(f"state stayed {updates.status()['state']}")


# ---------- versions ----------

def test_version_comparison():
    assert updates.is_newer("1.10.0", "1.9.9")
    assert updates.is_newer("2.0", "1.99.99")
    assert updates.is_newer("1.0.1", "1.0.0")
    assert not updates.is_newer("1.0.0", "1.0.0")
    assert not updates.is_newer("1.2", "1.2.0")
    assert not updates.is_newer("0.9.0", "1.0.0")
    for bad in ("", "v1.0", "1.0.0-beta", "1..0", None, 1, "1.2.3.4.5"):
        with pytest.raises(updates.UpdateError):
            updates.parse_version(bad)


# ---------- manifest verification ----------

def test_good_manifest_verifies():
    m = signed()
    assert updates.verify_manifest(m)["version"] == "99.0.0"


def test_signature_from_another_key_is_rejected():
    with pytest.raises(updates.UpdateError, match="firma"):
        updates.verify_manifest(signed(key=OTHER_KEY))


def test_unsigned_manifest_is_rejected():
    m = signed()
    m["signature"] = ""
    with pytest.raises(updates.UpdateError, match="firma"):
        updates.verify_manifest(m)
    del m["signature"]
    with pytest.raises(updates.UpdateError):
        updates.verify_manifest(m)


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", "99.0.1"),
        ("url", "https://evil.example/x.exe"),
        ("sha256", "0" * 64),
        ("size", len(INSTALLER) + 1),
        ("notes", "otra cosa"),
        ("published_at", "2030-01-01T00:00:00Z"),
    ],
)
def test_tampered_field_breaks_the_signature(field, value):
    m = signed()
    m[field] = value
    with pytest.raises(updates.UpdateError, match="firma"):
        updates.verify_manifest(m)


def test_malformed_manifests_are_rejected():
    for bad in (None, [], "x", signed(size="12"), signed(size=True), signed(sha256="ABC"), signed(version="v2")):
        with pytest.raises(updates.UpdateError):
            updates.verify_manifest(bad)


def test_license_signature_is_not_a_valid_manifest_signature():
    """Same key signs licenses: the domain prefix keeps the two message spaces apart."""
    m = signed()
    body = {k: m[k] for k in updates.SIGNED_FIELDS}
    plain = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    m["signature"] = b64(KEY.sign(plain))  # signature without the domain prefix
    with pytest.raises(updates.UpdateError, match="firma"):
        updates.verify_manifest(m)


def test_only_https_urls(monkeypatch):
    assert updates.check_url("https://github.com/o/r/releases/latest/download/latest.json")
    assert updates.check_url("http://127.0.0.1:8000/latest.json")  # development only
    for bad in ("http://example.com/latest.json", "ftp://example.com/x", "file:///C:/x.json", "https://", 5):
        with pytest.raises(updates.UpdateError):
            updates.check_url(bad)
    with pytest.raises(updates.UpdateError):
        updates.verify_manifest(signed(url="http://example.com/Bloom-Setup.exe"))
    monkeypatch.setattr(config, "FROZEN", True)
    with pytest.raises(updates.UpdateError):
        updates.check_url("http://127.0.0.1:8000/latest.json")


def test_manifest_url_env_override_only_in_development(monkeypatch):
    monkeypatch.setitem(config.BRAND, "updateManifest", "https://example.com/latest.json")
    monkeypatch.setenv("BLOOM_UPDATE_MANIFEST", "http://127.0.0.1:1/latest.json")
    assert updates.manifest_url() == "http://127.0.0.1:1/latest.json"
    monkeypatch.setattr(config, "FROZEN", True)
    assert updates.manifest_url() == "https://example.com/latest.json"
    monkeypatch.setitem(config.BRAND, "updateManifest", "")
    assert updates.manifest_url() is None


# ---------- check ----------

def test_check_finds_a_newer_version(server, monkeypatch):
    publish(server, monkeypatch)
    s = updates.check()
    assert s["available"] and s["latest"]["version"] == "99.0.0" and s["error"] is None
    assert s["latest"]["notes"].startswith("Mejoras")


@pytest.mark.parametrize("version", ["1.0.0", "0.9.0"])
def test_same_or_older_version_is_not_offered(server, monkeypatch, version):
    publish(server, monkeypatch, version=version)
    s = updates.check()
    assert not s["available"] and s["error"] is None and s["checked_at"]


def test_check_ignores_badly_signed_manifest(server, monkeypatch):
    m = signed(key=OTHER_KEY)
    monkeypatch.setenv("BLOOM_UPDATE_MANIFEST", server.json("/latest.json", m))
    s = updates.check()
    assert not s["available"] and "firma" in s["error"]


def test_check_rejects_redirect_to_http(server, monkeypatch):
    server.routes["/latest.json"] = (302, b"", {"Location": "http://example.com/latest.json"})
    monkeypatch.setenv("BLOOM_UPDATE_MANIFEST", f"{server.base}/latest.json")
    s = updates.check()
    assert not s["available"] and "https" in s["error"]


def test_offline_check_does_not_raise(monkeypatch):
    monkeypatch.setenv("BLOOM_UPDATE_MANIFEST", dead_url())
    s = updates.check()
    assert s["state"] == "idle" and not s["available"] and s["error"] == updates.MSG_OFFLINE


def dead_url() -> str:
    with socket.socket() as sock:  # a port nobody listens on
        sock.bind(("127.0.0.1", 0))
        return f"http://127.0.0.1:{sock.getsockname()[1]}/latest.json"


def test_offline_keeps_the_update_already_found(server, monkeypatch):
    publish(server, monkeypatch)
    assert updates.check()["available"]
    monkeypatch.setenv("BLOOM_UPDATE_MANIFEST", dead_url())
    s = updates.check()
    assert s["available"] and s["error"] == updates.MSG_OFFLINE


def test_not_configured(monkeypatch):
    s = updates.check()
    assert s["configured"] is False and s["error"] is None and not s["available"]


# ---------- download / install ----------

def test_download_verifies_sha256(server, monkeypatch, tmp_path):
    m = publish(server, monkeypatch)
    path = updates.download(updates.verify_manifest(m))
    assert path.read_bytes() == INSTALLER and path.name == "Bloom-Setup-99.0.0.exe"

    server.routes["/Bloom-Setup.exe"] = (200, INSTALLER[:-1] + b"X", {})
    with pytest.raises(updates.UpdateError, match="sha256"):
        updates.download(m)
    assert not any((tmp_path / "dl").iterdir())  # discarded


def test_download_rejects_size_mismatch(server, monkeypatch):
    m = publish(server, monkeypatch)
    server.routes["/Bloom-Setup.exe"] = (200, INSTALLER + b"extra", {})
    with pytest.raises(updates.UpdateError, match="tamaño"):
        updates.download(m)


def test_install_flow_backs_up_launches_and_exits(seeded, server, monkeypatch):
    client, admin = seeded
    publish(server, monkeypatch)
    launched, exited = [], threading.Event()
    monkeypatch.setattr(updates, "_launch_installer", lambda p: launched.append(p.read_bytes()) or True)
    updates.set_exit_handler(exited.set)
    before = {p.name for p in backup.list_backups()}

    assert client.post("/api/updates/check", headers=admin).json()["available"]
    r = client.post("/api/updates/install", headers=admin)
    assert r.status_code == 200, r.text
    s = wait_state("installing", "error")
    assert s["state"] == "installing", s
    assert exited.wait(5)
    assert launched == [INSTALLER]
    new = {p.name for p in backup.list_backups()} - before
    assert any(n.endswith("-pre-update.db") for n in new)
    assert s["progress"] == {"downloaded": len(INSTALLER), "total": len(INSTALLER)}


def test_install_from_source_verifies_but_does_not_run_installer(seeded, server, monkeypatch):
    client, admin = seeded
    publish(server, monkeypatch)
    updates.check()
    assert client.post("/api/updates/install", headers=admin).status_code == 200
    s = wait_state("ready", "error")
    assert s["state"] == "ready" and "desarrollo" in s["message"]


def test_install_with_sha_mismatch_fails_cleanly(seeded, server, monkeypatch):
    client, admin = seeded
    publish(server, monkeypatch)
    updates.check()
    server.routes["/Bloom-Setup.exe"] = (200, b"X" * len(INSTALLER), {})
    monkeypatch.setattr(updates, "_launch_installer", lambda p: pytest.fail("must not launch"))
    client.post("/api/updates/install", headers=admin)
    s = wait_state("error")
    assert "sha256" in s["error"]


def test_install_without_update_is_409(seeded):
    client, admin = seeded
    r = client.post("/api/updates/install", headers=admin)
    assert r.status_code == 409


def test_install_refuses_a_downgrade(seeded, monkeypatch):
    client, admin = seeded
    updates._state["latest"] = updates.verify_manifest(signed(version="0.5.0"))
    r = client.post("/api/updates/install", headers=admin)
    assert r.status_code == 409 and "más nueva" in r.json()["detail"]


# ---------- endpoints ----------

def test_endpoints_are_admin_only(seeded):
    client, admin = seeded
    caja = login(client, "Caja Demo", "1111")
    for method, path in (("get", "/api/updates"), ("post", "/api/updates/check"), ("post", "/api/updates/install")):
        assert getattr(client, method)(path).status_code == 401
        assert getattr(client, method)(path, headers=caja).status_code == 403
    r = client.get("/api/updates", headers=admin)
    assert r.status_code == 200
    body = r.json()
    assert body["current_version"] == "1.0.0" and body["state"] == "idle" and body["can_install"] is False


def test_app_version_comes_from_brand_json(client):
    brand = json.loads((config.BASE_DIR / "brand.json").read_text(encoding="utf-8"))
    assert config.BRAND["version"] == brand["version"]
    assert client.get("/api/health").json()["version"] == brand["version"]
