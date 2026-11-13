"""Current license status, computed from the stored token (cheap; cached briefly)."""

import json
import math
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.config import DATA_DIR, DB_PATH
from app.licensing import token as tok
from app.licensing.machine import machine_id

DAY = 86_400
# Tolerated backwards clock jump before the app asks to validate online.
CLOCK_SLACK_S = 6 * 3600
_CACHE_S = 30

_lock = threading.Lock()
_cache: tuple[float, "LicenseStatus"] | None = None


def token_path() -> Path:
    return DATA_DIR / "license.lic"


def state_path() -> Path:
    return DATA_DIR / "license_state.json"


@dataclass
class LicenseStatus:
    plan: str = "free"  # free | trial | pro
    valid: bool = False  # a paid/trial license is currently active
    features: list[str] = field(default_factory=list)
    customer: str | None = None
    license_id: str | None = None
    plan_key: str | None = None  # subscription plan (e.g. "pro_mensual"), for targeted announcements
    perpetual: bool = False
    expires_at: int | None = None  # paid/trial through
    grace_until: int | None = None
    in_grace: bool = False
    days_left: int | None = None
    machine_id: str = ""
    problem: str | None = None  # why a stored license isn't being honoured
    trial_ended: bool = False  # this PC already used its one Pro trial and it ran out
    # Plan limits signed into the token (e.g. {"tables": 10}); absent = no limit.
    limits: dict[str, int] = field(default_factory=dict)

    def has(self, feature: str) -> bool:
        return self.valid and ("*" in self.features or feature in self.features)

    def as_dict(self) -> dict:
        return asdict(self)


_evidence: tuple[float, float] | None = None  # (checked at, latest timestamp in the DB)


def db_clock_evidence() -> float:
    """Latest moment the business data proves we've reached (newest audit entry / sale).

    Deleting license_state.json resets `max_seen`, but the sales and audit log still prove the
    real date: a clock set before them is a rollback.
    """
    global _evidence
    now = time.monotonic()
    if _evidence and now - _evidence[0] < 60:
        return _evidence[1]
    latest = 0.0
    try:
        import sqlite3
        from datetime import UTC, datetime

        from contextlib import closing

        # closing(): "with sqlite3.connect()" only commits; a connection left open during a migration
        # or backup is asking for trouble.
        with closing(sqlite3.connect(f"file:{Path(DB_PATH).as_posix()}?mode=ro", uri=True, timeout=1)) as con:
            for table in ("audit_log", "sales"):
                try:
                    (value,) = con.execute(f"SELECT max(ts) FROM {table}").fetchone()  # noqa: S608  # nosec B608 - fixed table names
                except sqlite3.Error:
                    continue
                if value:
                    latest = max(latest, datetime.fromisoformat(str(value)).replace(tzinfo=UTC).timestamp())
    except Exception:
        latest = 0.0
    _evidence = (now, latest)
    return latest


def read_state() -> dict:
    try:
        data = json.loads(state_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_state(**changes) -> None:
    state = {**read_state(), **changes}
    try:
        state_path().write_text(json.dumps(state), encoding="utf-8")
    except OSError:
        pass


def parse_limits(raw) -> dict[str, int]:
    """Signed plan limits: only non-negative integers are honoured (anything else = no limit)."""
    if not isinstance(raw, dict):
        return {}
    return {str(k): v for k, v in raw.items() if isinstance(v, int) and not isinstance(v, bool) and v >= 0}


def evaluate(token: str | None, now: float | None = None) -> LicenseStatus:
    """Pure evaluation of a token at `now` for this machine (no caching, no I/O but the clock state)."""
    now_arg_missing = now is None
    now = time.time() if now is None else now
    status = LicenseStatus(machine_id=machine_id())
    if not token:
        return status
    try:
        p = tok.decode(token)
    except tok.TokenError as e:
        status.problem = str(e)
        return status

    status.customer = p.get("cust")
    status.license_id = p.get("lid")
    status.plan_key = p.get("pkey") if isinstance(p.get("pkey"), str) else None
    if p.get("mid") != status.machine_id:
        status.problem = "La licencia es de otra computadora. Activala de nuevo en esta."
        return status

    # A clock moved backwards could stretch an expiring license forever. Evidence: the latest time
    # this app saw, the latest data in the business DB, and when the license itself was issued.
    real_clock = now_arg_missing
    max_seen = max(float(read_state().get("max_seen", 0)), db_clock_evidence() if real_clock else 0.0)
    issued = float(p.get("iat") or 0)
    if now < max_seen - CLOCK_SLACK_S or now < issued - CLOCK_SLACK_S:
        status.problem = "La fecha de la computadora está atrasada. Corregila o conectate a internet para validar la licencia."
        return status

    exp = p.get("exp")
    grace_days = int(p.get("grace", 0))
    status.plan = "trial" if p.get("plan") == "trial" else "pro"
    status.features = list(p.get("features") or [])
    status.limits = parse_limits(p.get("limits"))
    status.perpetual = exp is None
    if exp is not None:
        status.expires_at = int(exp)
        status.grace_until = int(exp) + grace_days * DAY
        if now > status.grace_until:
            status.trial_ended = status.plan == "trial"
            status.problem = (
                "Terminó la prueba gratuita." if status.plan == "trial" else "La suscripción venció."
            )
            status.plan = "free"
            status.features = []
            return status
        status.in_grace = now > exp
        status.days_left = max(0, math.ceil(((status.grace_until if status.in_grace else exp) - now) / DAY))
    status.valid = True
    return status


def current_status(force: bool = False) -> LicenseStatus:
    global _cache
    from app import demo

    if demo.is_enabled():  # online demo (never the desktop build): every Pro feature, no license file
        return demo.demo_license_status()
    now = time.time()
    with _lock:
        if not force and _cache and now - _cache[0] < _CACHE_S:
            return _cache[1]
        try:
            token = token_path().read_text(encoding="utf-8").strip()
        except OSError:
            token = None
        status = evaluate(token, now)
        if status.valid and now > float(read_state().get("max_seen", 0)):
            write_state(max_seen=now)
        _cache = (now, status)
        return status


def store_token(token: str | None) -> LicenseStatus:
    """Saves (or removes) the license and returns the fresh status."""
    if token:
        token_path().write_text(token.strip(), encoding="utf-8")
    else:
        token_path().unlink(missing_ok=True)
    return current_status(force=True)
