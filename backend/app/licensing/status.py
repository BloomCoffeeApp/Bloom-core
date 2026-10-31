"""Current license status, computed from the stored token (cheap; cached briefly)."""

import json
import math
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.config import DATA_DIR
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
    perpetual: bool = False
    expires_at: int | None = None  # paid/trial through
    grace_until: int | None = None
    in_grace: bool = False
    days_left: int | None = None
    machine_id: str = ""
    problem: str | None = None  # why a stored license isn't being honoured

    def has(self, feature: str) -> bool:
        return self.valid and ("*" in self.features or feature in self.features)

    def as_dict(self) -> dict:
        return asdict(self)


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


def evaluate(token: str | None, now: float | None = None) -> LicenseStatus:
    """Pure evaluation of a token at `now` for this machine (no caching, no I/O but the clock state)."""
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
    if p.get("mid") != status.machine_id:
        status.problem = "La licencia es de otra computadora. Activala de nuevo en esta."
        return status

    # A clock moved backwards could stretch an expiring license forever.
    max_seen = float(read_state().get("max_seen", 0))
    if now < max_seen - CLOCK_SLACK_S:
        status.problem = "La fecha de la computadora está atrasada. Corregila o conectate a internet para validar la licencia."
        return status

    exp = p.get("exp")
    grace_days = int(p.get("grace", 0))
    status.plan = "trial" if p.get("plan") == "trial" else "pro"
    status.features = list(p.get("features") or [])
    status.perpetual = exp is None
    if exp is not None:
        status.expires_at = int(exp)
        status.grace_until = int(exp) + grace_days * DAY
        if now > status.grace_until:
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
