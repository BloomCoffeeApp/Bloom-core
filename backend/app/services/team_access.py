"""Team code for the staff phone app (`/equipo`).

The QR at the register carries a short code (`{lan_url}/equipo?k=<code>`). Without it the phone cannot even see
the list of staff names; with it a person picks their name and types their PIN (the normal login, flagged as
`client="equipo"`). The code rotates by itself once a day (local date) or only by hand, as the owner prefers.

Stored in the `team_access` setting, which is NOT in `settings.DEFAULTS`: `GET /api/settings` hands every
setting to any logged-in user and the code must not travel there.
"""
import secrets
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import User
from app.services import roles, timeutil
from app.services import settings as settings_svc

SETTING = "team_access"
# Anyone holding one of these is shown on the phone login (admin always holds all of them).
TEAM_PERMS = ("tables.serve", "kitchen.use", "stock.receive")
ROTATE_MODES = ("daily", "manual")
DEFAULT_LOCK_MINUTES = 30


def new_key() -> str:
    return secrets.token_urlsafe(9)  # 12 chars, ~72 bits (same as the table QR token)


def _raw(db: Session) -> dict[str, Any]:
    return dict(settings_svc.get(db, SETTING) or {})


def config(db: Session) -> dict[str, Any]:
    """Current config; creates the code on first use and renews it when it is a new local day (daily mode)."""
    cur = _raw(db)
    today = timeutil.local_today().isoformat()
    changed = False
    if not cur.get("key"):
        cur["key"], cur["rotated_on"], changed = new_key(), today, True
    cur.setdefault("rotate", "daily")
    cur.setdefault("lock_minutes", DEFAULT_LOCK_MINUTES)
    if cur["rotate"] == "daily" and cur.get("rotated_on") != today:
        cur["key"], cur["rotated_on"], changed = new_key(), today, True
    if changed:
        settings_svc.put(db, SETTING, cur)
        db.commit()
    return cur


def rotate(db: Session) -> str:
    cur = config(db)
    cur["key"], cur["rotated_on"] = new_key(), timeutil.local_today().isoformat()
    settings_svc.put(db, SETTING, cur)
    return cur["key"]


def save(db: Session, rotate_mode: str | None, lock_minutes: int | None) -> dict[str, Any]:
    cur = config(db)
    if rotate_mode is not None:
        if rotate_mode not in ROTATE_MODES:
            raise HTTPException(422, "Rotación inválida")
        cur["rotate"] = rotate_mode
    if lock_minutes is not None:
        if not 1 <= lock_minutes <= 480:
            raise HTTPException(422, "El bloqueo por inactividad va de 1 a 480 minutos")
        cur["lock_minutes"] = lock_minutes
    settings_svc.put(db, SETTING, cur)
    return cur


def valid(db: Session, key: str | None) -> bool:
    if not key:
        return False
    return secrets.compare_digest(str(config(db)["key"]).encode(), key.encode())


def team_users(db: Session) -> list[User]:
    """Active people who may use the staff app: anyone with a waiter / kitchen / warehouse permission."""
    from sqlalchemy import select

    return [u for u in db.scalars(select(User).where(User.active.is_(True)).order_by(User.name))
            if roles.has(u, *TEAM_PERMS)]


def can_use(user: User) -> bool:
    return roles.has(user, *TEAM_PERMS)
