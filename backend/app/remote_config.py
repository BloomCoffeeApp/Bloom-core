"""Remote configuration signed by the vendor's license server (GET <licenseServer>/v1/config).

Only the server address (brand.json `licenseServer`) and the Ed25519 public key are built into the
app; everything else the vendor may change without a new .exe comes from here: the update manifest
URL, the minimum supported version, release notes link, support contacts, legal links and the
announcements shown in the app.

Envelope: {"payload": {...}, "signature": "<base64url>"} where
signature = Ed25519(b"BLOOM-CONFIG1\\n" + canonical JSON of payload) with the same vendor key as
licenses (verified with the public key the app embeds; never with anything the server sends).

Rules: a fetched config must be signed, not expired (`exp`), not from the far future (`iat`) and not
older than the one already cached (no replay of an old config). The verified envelope is cached in
the data dir and used offline (even after `exp`: it's still the vendor's latest word). Nothing here
ever raises into the app.
"""

import json
import logging
import threading
import time
from pathlib import Path

from app.config import DATA_DIR

log = logging.getLogger("cafeteria.remote_config")

DOMAIN = b"BLOOM-CONFIG1\n"
REFRESH_EVERY_S = 6 * 3600
RETRY_AFTER_ERROR_S = 1800
STARTUP_DELAY_S = 20
MAX_FUTURE_S = 86_400  # tolerated clock difference for `iat`
LEVELS = ("info", "warning", "critical")

_lock = threading.Lock()
_state: dict = {"payload": None, "loaded": False, "checked_at": 0.0, "error": None}


class ConfigError(Exception):
    pass


def cache_path() -> Path:
    return DATA_DIR / "remote_config.json"


def canonical_message(payload: dict) -> bytes:
    return DOMAIN + json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def verify(envelope: object, now: float | None = None, *, newer_than: int | None = None,
           allow_expired: bool = False) -> dict:
    """Returns the payload if signed by the vendor and acceptable; raises ConfigError."""
    from cryptography.exceptions import InvalidSignature

    from app.licensing.token import TokenError, b64d, public_key

    now = time.time() if now is None else now
    if not isinstance(envelope, dict) or not isinstance(envelope.get("payload"), dict):
        raise ConfigError("Configuración remota inválida")
    payload, sig = envelope["payload"], envelope.get("signature")
    if not isinstance(sig, str) or not sig:
        raise ConfigError("Configuración remota sin firma")
    try:
        public_key().verify(b64d(sig), canonical_message(payload))
    except (InvalidSignature, ValueError, TokenError) as e:
        raise ConfigError("La firma de la configuración remota no es válida") from e
    iat, exp = payload.get("iat"), payload.get("exp")
    if payload.get("v") != 1 or not isinstance(iat, int) or not isinstance(exp, int):
        raise ConfigError("Versión de configuración remota no soportada")
    if iat > now + MAX_FUTURE_S:
        raise ConfigError("La configuración remota tiene fecha futura")
    if not allow_expired and exp < now:
        raise ConfigError("La configuración remota venció")
    if newer_than is not None and iat < newer_than:
        raise ConfigError("La configuración remota es más vieja que la guardada")
    return payload


def _load_cache() -> dict | None:
    try:
        envelope = json.loads(cache_path().read_text(encoding="utf-8"))
        return verify(envelope, allow_expired=True)
    except (OSError, ValueError, ConfigError) as e:
        if cache_path().exists():
            log.warning("Ignoring cached remote config: %s", e)
        return None


def current() -> dict | None:
    """The latest verified payload (memory, else the cache on disk), or None."""
    with _lock:
        if not _state["loaded"]:
            _state["payload"], _state["loaded"] = _load_cache(), True
        return _state["payload"]


def _store(envelope: dict, payload: dict) -> None:
    tmp = cache_path().with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
        tmp.replace(cache_path())
    except OSError:
        log.exception("Could not cache the remote config")
    with _lock:
        _state.update(payload=payload, loaded=True)


def fetch() -> dict | None:
    """Downloads, verifies and caches the config. Returns the payload; raises ConfigError."""
    from app.licensing import client

    if not client.server_url():
        return None
    try:
        envelope = client._get("/v1/config")
    except client.LicenseServerError as e:
        raise ConfigError(str(e)) from e
    cached = current()
    payload = verify(envelope, newer_than=cached.get("iat") if cached else None)
    _store(envelope, payload)
    return payload


def refresh_if_due(now: float | None = None) -> None:
    """Background job: every 6 h (30 min after an error). Silent offline."""
    from app.licensing import client

    if not client.server_url():
        return
    now = time.time() if now is None else now
    with _lock:
        wait = RETRY_AFTER_ERROR_S if _state["error"] else REFRESH_EVERY_S
        if _state["checked_at"] and now - _state["checked_at"] < wait:
            return
        _state["checked_at"] = now
    try:
        fetch()
        _state["error"] = None
    except ConfigError as e:
        _state["error"] = str(e)
        log.info("Remote config not refreshed: %s", e)
    except Exception:
        _state["error"] = "unexpected"
        log.exception("Remote config refresh failed")


def reset() -> None:
    """Tests only."""
    with _lock:
        _state.update(payload=None, loaded=False, checked_at=0.0, error=None)


# ---------------------------------------------------------------- accessors (never raise)


def _section(name: str) -> dict:
    p = current() or {}
    value = p.get(name)
    return value if isinstance(value, dict) else {}


def _str(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def free_limits() -> dict:
    return _section("free_limits")


def manifest_url() -> str | None:
    return _str(_section("updates").get("manifest_url"))


def min_version() -> str | None:
    return _str(_section("updates").get("min_version"))


def release_notes_url() -> str | None:
    url = _str(_section("updates").get("release_notes_url"))
    return url if url and url.startswith("https://") else None


def support() -> dict:
    s = _section("support")
    out = {k: _str(s.get(k)) for k in ("email", "whatsapp", "terms_url", "privacy_url")}
    for k in ("terms_url", "privacy_url"):
        if out[k] and not out[k].startswith("https://"):
            out[k] = None
    return out


def _parse_ts(value: object) -> float | None:
    from datetime import datetime

    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _targets_me(target: str, status) -> bool:
    if target in ("all", ""):
        return True
    if target == "free":
        return not status.valid
    if target == "trial":
        return status.valid and status.plan == "trial"
    if target == "pro":
        return status.valid and status.plan == "pro"
    if target.startswith("plan:"):
        return status.valid and status.plan_key == target[5:]
    return False


def announcements(status=None, now: float | None = None) -> list[dict]:
    """Announcements for this installation right now (date window + target)."""
    from app.licensing import current_status

    status = status or current_status()
    now = time.time() if now is None else now
    out = []
    for a in (current() or {}).get("announcements") or []:
        if not isinstance(a, dict) or not isinstance(a.get("id"), int) or not _str(a.get("title")):
            continue
        start, end = _parse_ts(a.get("starts_at")), _parse_ts(a.get("ends_at"))
        if (start and now < start) or (end and now >= end):
            continue
        if not _targets_me(str(a.get("target") or "all"), status):
            continue
        level = a.get("level") if a.get("level") in LEVELS else "info"
        out.append({"id": a["id"], "title": str(a["title"])[:120], "body": str(a.get("body") or "")[:2000],
                    "level": level})
    return out
