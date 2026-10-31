"""In-app updates: check a signed manifest, download the installer, verify it and run it.

Provider-agnostic: the app only knows the manifest URL (brand.json `updateManifest`), e.g. a
GitHub "latest release" asset or a proxy on the license server. Manifest (latest.json):

    {"version": "1.2.0", "url": "https://.../Bloom-Setup-1.2.0.exe", "sha256": "<hex>",
     "size": 123456, "notes": "...", "published_at": "2026-01-31T12:00:00Z", "signature": "<b64url>"}

`signature` is Ed25519 over `BLOOM-UPDATE1\\n` + the canonical JSON of the other six fields
(sorted keys, no spaces, UTF-8), signed with the vendor's license key and verified with the
public key the app already embeds for licenses. The domain prefix keeps a manifest signature
from ever being valid as a license token (those sign `BLOOM1.<payload>`) and vice versa.

Rules: only https URLs (http://127.0.0.1 / localhost only in development), unsigned or badly
signed manifests are ignored, only strictly newer versions are offered, and the download must
match `size` and `sha256` exactly. Nothing here raises into the app: being offline only shows
a message in Configuración → Acerca de.
"""

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from app import config

log = logging.getLogger("cafeteria.updates")

DOMAIN = b"BLOOM-UPDATE1\n"
SIGNED_FIELDS = ("version", "url", "sha256", "size", "notes", "published_at")
CHECK_TIMEOUT_S = 20
DOWNLOAD_TIMEOUT_S = 60  # per network read
MAX_MANIFEST_BYTES = 64 * 1024
MAX_INSTALLER_BYTES = 600 * 1024 * 1024
CHECK_EVERY_S = 6 * 3600
STARTUP_DELAY_S = 90
EXIT_DELAY_S = 2.0  # lets the UI see "installing" before the window closes
INSTALLER_ARGS = ("/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/UPDATE=1")
BUSY = ("checking", "downloading", "verifying", "installing")

_VERSION_RE = re.compile(r"^\d{1,6}(\.\d{1,6}){0,3}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

MSG_OFFLINE = "No se pudo conectar para buscar actualizaciones. Revisá la conexión a internet."
MSG_BAD_SIGNATURE = "La actualización publicada no tiene una firma válida, así que se ignoró."
MSG_INVALID = "El aviso de actualización no es válido."


class UpdateError(Exception):
    pass


# ---------- versions ----------

def parse_version(v: object) -> tuple[int, int, int, int]:
    if not isinstance(v, str) or not _VERSION_RE.match(v.strip()):
        raise UpdateError(f"Versión inválida: {v!r}")
    parts = [int(p) for p in v.strip().split(".")]
    return tuple(parts + [0] * (4 - len(parts)))  # type: ignore[return-value]


def is_newer(candidate: str, current: str) -> bool:
    return parse_version(candidate) > parse_version(current)


# ---------- URLs ----------

def manifest_url() -> str | None:
    """brand.json `updateManifest`; BLOOM_UPDATE_MANIFEST overrides it only in development."""
    if not config.FROZEN and "BLOOM_UPDATE_MANIFEST" in os.environ:
        return os.environ["BLOOM_UPDATE_MANIFEST"].strip() or None
    url = config.BRAND.get("updateManifest")
    return url.strip() if isinstance(url, str) and url.strip() else None


def check_url(url: object) -> str:
    if not isinstance(url, str):
        raise UpdateError("Dirección de actualización inválida")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme == "https" and parsed.hostname:
        return url
    if parsed.scheme == "http" and not config.FROZEN and parsed.hostname in _LOCAL_HOSTS:
        return url  # local test server (development only)
    raise UpdateError("Dirección de actualización no permitida: tiene que ser https")


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    """Release hosts redirect downloads (e.g. to a CDN); never let that downgrade to http."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_SafeRedirect)


def _open(url: str, timeout: float):
    req = urllib.request.Request(
        check_url(url), headers={"User-Agent": f"{config.APP_ID}/{config.APP_VERSION}", "Accept": "*/*"}
    )
    return _opener.open(req, timeout=timeout)


# ---------- manifest ----------

def canonical_message(manifest: dict) -> bytes:
    body = {k: manifest[k] for k in SIGNED_FIELDS}
    return DOMAIN + json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def verify_manifest(manifest: object) -> dict:
    """Returns the manifest (signed fields + signature) if well-formed and signed; raises UpdateError."""
    from cryptography.exceptions import InvalidSignature

    from app.licensing.token import TokenError, b64d, public_key

    if not isinstance(manifest, dict):
        raise UpdateError(MSG_INVALID)
    missing = [k for k in (*SIGNED_FIELDS, "signature") if k not in manifest]
    if missing:
        raise UpdateError(f"{MSG_INVALID} Faltan: {', '.join(missing)}")
    m = {k: manifest[k] for k in (*SIGNED_FIELDS, "signature")}
    if not all(isinstance(m[k], str) for k in ("version", "url", "sha256", "notes", "published_at", "signature")):
        raise UpdateError(MSG_INVALID)
    if not isinstance(m["size"], int) or isinstance(m["size"], bool) or not 0 < m["size"] <= MAX_INSTALLER_BYTES:
        raise UpdateError(MSG_INVALID)
    if not _SHA_RE.match(m["sha256"]):
        raise UpdateError(MSG_INVALID)
    parse_version(m["version"])
    if not m["signature"]:
        raise UpdateError(MSG_BAD_SIGNATURE)
    try:
        public_key().verify(b64d(m["signature"]), canonical_message(m))
    except (InvalidSignature, ValueError, TokenError) as e:
        raise UpdateError(MSG_BAD_SIGNATURE) from e
    check_url(m["url"])  # after the signature: the URL is vendor-controlled, but still https only
    return m


def fetch_manifest(url: str) -> dict:
    try:
        with _open(url, CHECK_TIMEOUT_S) as r:
            raw = r.read(MAX_MANIFEST_BYTES + 1)
    except UpdateError:
        raise
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise UpdateError("Todavía no hay versiones publicadas.") from e
        raise UpdateError(f"El servidor de actualizaciones respondió {e.code}.") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise UpdateError(MSG_OFFLINE) from e
    if len(raw) > MAX_MANIFEST_BYTES:
        raise UpdateError(MSG_INVALID)
    try:
        return json.loads(raw)
    except ValueError as e:
        raise UpdateError(MSG_INVALID) from e


# ---------- state ----------

_lock = threading.Lock()
_state: dict = {}
_exit_handler: Callable[[], None] | None = None


def _reset_state() -> None:
    _state.clear()
    _state.update(state="idle", latest=None, checked_at=None, error=None, message=None, downloaded=0, total=0)


_reset_state()


def set_exit_handler(fn: Callable[[], None] | None) -> None:
    """The desktop launcher registers how to close the app so the installer can replace it."""
    global _exit_handler
    _exit_handler = fn


def _set(**kw) -> None:
    with _lock:
        _state.update(kw)


def _describe(s: dict) -> dict:
    latest = s["latest"]
    return {
        "current_version": config.APP_VERSION,
        "configured": manifest_url() is not None,
        "state": s["state"],
        "available": latest is not None,
        "latest": {k: latest[k] for k in ("version", "notes", "published_at", "size")} if latest else None,
        "checked_at": s["checked_at"],
        "error": s["error"],
        "message": s["message"],
        "progress": {"downloaded": s["downloaded"], "total": s["total"]},
        "can_install": bool(config.FROZEN),
    }


def status() -> dict:
    with _lock:
        snapshot = dict(_state)
    return _describe(snapshot)


def check() -> dict:
    """Fetches and verifies the manifest. Never raises: problems end up in `error`."""
    url = manifest_url()
    if not url:
        _set(error=None)
        return status()
    with _lock:
        busy = _state["state"] in BUSY
        if not busy:
            _state.update(state="checking", error=None, message=None)
    if busy:
        return status()
    try:
        manifest = verify_manifest(fetch_manifest(url))
        latest = manifest if is_newer(manifest["version"], config.APP_VERSION) else None
        _set(state="idle", latest=latest, checked_at=datetime.now(UTC), error=None)
        if latest:
            log.info("Update available: %s -> %s", config.APP_VERSION, latest["version"])
    except UpdateError as e:
        log.info("Update check failed: %s", e)
        _set(state="idle", checked_at=datetime.now(UTC), error=str(e))
    except Exception:
        log.exception("Update check failed")
        _set(state="idle", checked_at=datetime.now(UTC), error=MSG_INVALID)
    return status()


RETRY_AFTER_ERROR_S = 1800


def check_if_due() -> None:
    with _lock:
        checked, failed = _state["checked_at"], _state["error"] is not None
    wait = RETRY_AFTER_ERROR_S if failed else CHECK_EVERY_S
    if checked is None or (datetime.now(UTC) - checked).total_seconds() >= wait:
        check()


# ---------- install ----------

def download_dir() -> Path:
    return Path(tempfile.gettempdir()) / f"{config.APP_ID}-update"


def download(manifest: dict, progress: Callable[[int, int], None] | None = None) -> Path:
    """Streams the installer to a temp folder; checks size and sha256. Returns its path."""
    folder = download_dir()
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True, exist_ok=True)
    exe = str(config.BRAND.get("exeName") or config.APP_DISPLAY_NAME)
    dest = folder / f"{re.sub(r'[^A-Za-z0-9_-]', '', exe) or 'app'}-Setup-{manifest['version']}.exe"
    size = manifest["size"]
    h = hashlib.sha256()
    done = 0
    try:
        with _open(manifest["url"], DOWNLOAD_TIMEOUT_S) as r, dest.open("wb") as f:
            length = r.headers.get("Content-Length")
            if length and length.isdigit() and int(length) != size:
                raise UpdateError("El tamaño del archivo publicado no coincide con el aviso de actualización.")
            while chunk := r.read(256 * 1024):
                done += len(chunk)
                if done > size:
                    raise UpdateError("El archivo descargado es más grande de lo esperado; se descartó.")
                h.update(chunk)
                f.write(chunk)
                if progress:
                    progress(done, size)
    except UpdateError:
        dest.unlink(missing_ok=True)
        raise
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        dest.unlink(missing_ok=True)
        raise UpdateError("Se cortó la descarga de la actualización. Probá de nuevo.") from e
    if done != size:
        dest.unlink(missing_ok=True)
        raise UpdateError("La descarga quedó incompleta. Probá de nuevo.")
    if h.hexdigest() != manifest["sha256"]:
        dest.unlink(missing_ok=True)
        raise UpdateError("El archivo descargado no coincide con el publicado (sha256); se descartó.")
    return dest


def _launch_installer(path: Path) -> bool:
    """Runs the installer detached. Only the packaged app does it: from source it would install
    the packaged edition over this PC's real installation."""
    if not config.FROZEN:
        log.info("Development: verified installer %s not launched", path)
        return False
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(  # noqa: S603 — path built by us, file verified against the signed sha256
        [str(path), *INSTALLER_ARGS, f"/LOG={path.with_suffix('.log')}"],
        cwd=str(path.parent),
        creationflags=flags,
        close_fds=True,
    )
    return True


def _request_exit() -> None:
    if _exit_handler is None:
        log.warning("Installer launched but no exit handler: the user has to close the app")
        return
    try:
        _exit_handler()
    except Exception:
        log.exception("Exit handler failed")


def _backup_before_update() -> None:
    from app.services import backup

    if config.DB_PATH.exists() and config.DB_PATH.stat().st_size > 0:
        backup.create_backup("pre-update")
        backup.prune(40)


def _install(manifest: dict) -> None:
    try:
        verify_manifest(manifest)
        path = download(manifest, progress=lambda d, t: _set(downloaded=d, total=t))
        _set(state="verifying")
        _backup_before_update()
        _set(state="installing", message="Instalando la actualización. La aplicación se va a cerrar y volver a abrir.")
        if _launch_installer(path):
            log.info("Installer for %s launched; closing the app", manifest["version"])
            threading.Timer(EXIT_DELAY_S, _request_exit).start()
        else:
            _set(state="ready", message="Actualización descargada y verificada. En modo desarrollo no se ejecuta el instalador.")
    except UpdateError as e:
        log.warning("Update failed: %s", e)
        _set(state="error", error=str(e), message=None)
    except Exception:
        log.exception("Update failed")
        _set(state="error", error="No se pudo instalar la actualización. Probá de nuevo más tarde.", message=None)


def start_install() -> dict:
    """Starts download + install in the background; poll `status()` for progress."""
    with _lock:
        if _state["state"] in BUSY:
            raise UpdateError("Ya hay una actualización en curso.")
        latest = _state["latest"]
        if not latest:
            raise UpdateError("No hay ninguna actualización disponible.")
        if not is_newer(latest["version"], config.APP_VERSION):
            raise UpdateError("Esa versión no es más nueva que la instalada.")
        _state.update(state="downloading", error=None, message=None, downloaded=0, total=latest["size"])
    threading.Thread(target=_install, args=(latest,), name="app-update", daemon=True).start()
    return status()
