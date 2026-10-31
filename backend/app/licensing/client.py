"""Talks to the vendor's license server (activation, trial, renewal). Stdlib only."""

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from app.config import APP_VERSION, BRAND
from app.licensing.machine import machine_id, machine_name
from app.licensing.status import (
    LicenseStatus,
    current_status,
    evaluate,
    read_state,
    store_token,
    token_path,
    write_state,
)

log = logging.getLogger("cafeteria.license")
# Free hosting (e.g. Render) sleeps when idle and takes up to ~1 min to wake up.
TIMEOUT_S = 75
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


def _get(path: str, query: dict | None = None) -> dict:
    url = server_url()
    if not url:
        raise LicenseServerError("Esta instalación no tiene servidor de licencias configurado.")
    qs = f"?{urllib.parse.urlencode(query)}" if query else ""
    req = urllib.request.Request(f"{url}{path}{qs}", headers={"User-Agent": f"{BRAND.get('appId')}/{APP_VERSION}"})
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
    # Validate before saving: a bad token must never replace a working license.
    problem = evaluate(token).problem
    if problem:
        raise LicenseServerError(problem)
    status = store_token(token)
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


# ---------------------------------------------------------------- subscriptions (paid in Mercado Pago)


def plans() -> dict:
    return _get("/v1/plans")


def start_checkout(plan: str, email: str, business_name: str | None) -> dict:
    """Returns {checkout_id, url}: the url is Mercado Pago's payment page."""
    resp = _post("/v1/checkout", {"plan": plan, "email": email, "business_name": business_name, **_device()})
    # Remembered so the license still activates if the app is closed while paying.
    write_state(pending_checkout={"id": resp["checkout_id"], "at": time.time()})
    return resp


def checkout_status(checkout_id: str) -> dict:
    """Polled by the app while the customer pays; activates the license as soon as it's authorized."""
    resp = _get(f"/v1/checkout/{urllib.parse.quote(checkout_id)}", {"machine_id": machine_id()})
    out = {"status": resp.get("status", "pending"), "key": resp.get("key")}
    if resp.get("token"):
        out["license"] = _accept(resp).as_dict()
    if out.get("license") or out["status"] == "cancelled":
        write_state(pending_checkout=None)
    return out


def _token_body() -> dict:
    try:
        token = token_path().read_text(encoding="utf-8").strip()
    except OSError as e:
        raise LicenseServerError("Esta computadora no tiene una licencia activa.") from e
    return {"token": token, "machine_id": machine_id()}


def subscription() -> dict:
    """The automatic-charge subscription behind this license (plan, status, paid date)."""
    return _post("/v1/subscription", _token_body())


def cancel_subscription() -> dict:
    """'Botón de baja': stops future charges; the time already paid keeps working."""
    resp = _post("/v1/subscription/cancel", _token_body())
    try:  # the paid date doesn't change, but keep the local token fresh
        refresh()
    except LicenseServerError as e:
        log.info("Refresh after cancelling skipped: %s", e)
    return resp


PENDING_CHECKOUT_DAYS = 7


def pending_checkout_id() -> str | None:
    pending = read_state().get("pending_checkout") or {}
    if pending.get("id") and time.time() - float(pending.get("at", 0)) < PENDING_CHECKOUT_DAYS * 86_400:
        return str(pending["id"])
    return None


def check_pending_checkout() -> None:
    """Background job: finishes an activation whose payment completed while the app wasn't looking."""
    checkout_id = pending_checkout_id()
    if not checkout_id or not server_url():
        return
    try:
        checkout_status(checkout_id)
    except LicenseServerError as e:
        log.info("Pending checkout not resolved yet: %s", e)
