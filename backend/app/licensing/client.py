"""Talks to the vendor's license server (activation, trial, renewal). Stdlib only."""

import json
import logging
import os
import time
import urllib.error
import urllib.request

from app.config import APP_VERSION, BRAND
from app.licensing.machine import machine_id, machine_name
from app.licensing.status import LicenseStatus, current_status, read_state, store_token, token_path, write_state

log = logging.getLogger("cafeteria.license")
TIMEOUT_S = 12
# Renew in the background at most this often (tokens are re-signed with the latest paid date).
REFRESH_EVERY_S = 12 * 3600


class LicenseServerError(Exception):
    pass


def server_url() -> str | None:
    url = os.environ.get("BLOOM_LICENSE_SERVER") or BRAND.get("licenseServer")
    return url.rstrip("/") if url else None


def _post(path: str, body: dict) -> dict:
    url = server_url()
    if not url:
        raise LicenseServerError("Esta instalación no tiene servidor de licencias configurado.")
    req = urllib.request.Request(
        f"{url}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "User-Agent": f"{BRAND.get('appId')}/{APP_VERSION}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read()).get("detail")
        except Exception:
            detail = None
        raise LicenseServerError(detail or f"El servidor de licencias respondió {e.code}.") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise LicenseServerError("No se pudo conectar con el servidor de licencias. Revisá la conexión a internet.") from e


def _device() -> dict:
    return {"machine_id": machine_id(), "machine_name": machine_name(), "app_version": APP_VERSION}


def _accept(resp: dict) -> LicenseStatus:
    token = resp.get("token")
    if not token:
        raise LicenseServerError("Respuesta inválida del servidor de licencias.")
    status = store_token(token)
    if status.problem:
        raise LicenseServerError(status.problem)
    write_state(last_refresh=time.time(), last_error=None)
    return status


def activate(key: str) -> LicenseStatus:
    return _accept(_post("/v1/activate", {"key": key.strip(), **_device()}))


def start_trial() -> LicenseStatus:
    return _accept(_post("/v1/trial", _device()))


def refresh() -> LicenseStatus:
    try:
        token = token_path().read_text(encoding="utf-8").strip()
    except OSError:
        return current_status()
    try:
        return _accept(_post("/v1/refresh", {"token": token, **_device()}))
    except LicenseServerError as e:
        write_state(last_error=str(e))
        raise


def deactivate() -> LicenseStatus:
    """Frees this computer's seat on the server (best effort) and removes the local license."""
    try:
        token = token_path().read_text(encoding="utf-8").strip()
        _post("/v1/deactivate", {"token": token, **_device()})
    except (OSError, LicenseServerError) as e:
        log.warning("Deactivation not confirmed by the server: %s", e)
    return store_token(None)


def refresh_if_due() -> None:
    """Called by the background jobs; silent when offline (the grace period covers it)."""
    if not token_path().exists() or not server_url():
        return
    state, now = read_state(), time.time()
    if now - float(state.get("last_refresh", 0)) < REFRESH_EVERY_S or now - float(state.get("last_attempt", 0)) < 3600:
        return
    write_state(last_attempt=now)
    try:
        refresh()
    except LicenseServerError as e:
        log.info("License refresh skipped: %s", e)
