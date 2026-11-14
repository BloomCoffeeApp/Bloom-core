"""Staff phone app (`/equipo`): the team code in the register's QR, the public staff list behind it, per-session
lock time. Login itself is `/api/auth/login` with `client="equipo"` (routers/auth.py)."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import CurrentUser, Perm, login_throttle
from app.db import get_db
from app.licensing import require_feature
from app.models import User
from app.schemas.users import UserPublic
from app.services import audit, free_plan, roles, system as system_svc, team_access

router = APIRouter(prefix="/api/team", tags=["team"])
Show = Perm("pos.sell", "orders.manage", "tables.serve", "settings.manage")
Manage = Perm("orders.manage", "settings.manage")


class TeamConfigIn(BaseModel):
    rotate: str | None = None
    lock_minutes: int | None = None


class TeamStatus(BaseModel):
    ok: bool


def _url(db: Session) -> str | None:
    base = system_svc.lan_url()
    return f"{base}/equipo?k={team_access.config(db)['key']}" if base else None


def _check_key(db: Session, request: Request, key: str | None) -> None:
    """Public endpoints behind the code: a wrong code costs a throttle strike per client IP."""
    ip = f"team:{request.client.host if request.client else '?'}"
    if wait := login_throttle.wait_seconds(ip):
        raise HTTPException(429, f"Demasiados intentos. Probá de nuevo en {wait} segundos.")
    if not team_access.valid(db, key):
        login_throttle.fail(ip)
        raise HTTPException(403, "El código del equipo no es válido. Escaneá de nuevo el QR de la caja.")
    login_throttle.success(ip)


def check_login_key(db: Session, request: Request, key: str | None) -> None:
    """Used by `/api/auth/login` when `client == "equipo"`."""
    _check_key(db, request, key)


@router.get("/info", dependencies=[Depends(require_feature("lan"))])
def info(db: Session = Depends(get_db), _: User = Show) -> dict:
    """What the cashier sees: where the QR points, whether Wi-Fi mode is on, and the rotation setting."""
    cfg = team_access.config(db)
    data = system_svc.info(db)
    return {
        "url": _url(db), "lan_enabled": data["lan_enabled"], "lan_active": data["lan_active"],
        "network_public": data["network_public"], "rotate": cfg["rotate"], "lock_minutes": cfg["lock_minutes"],
        "rotated_on": cfg.get("rotated_on"),
    }


@router.get("/qr", dependencies=[Depends(require_feature("lan"))])
def qr(db: Session = Depends(get_db), _: User = Show) -> Response:
    url = _url(db)
    if not url:
        raise HTTPException(404, "No se encontró una red local")
    return Response(content=system_svc.qr_png(url), media_type="image/png", headers={"Cache-Control": "no-store"})


@router.post("/rotate")
def rotate(db: Session = Depends(get_db), me: User = Manage) -> dict:
    team_access.rotate(db)
    audit.log(db, me.id, "rotate", "team_access", None)
    db.commit()
    return {"ok": True}


@router.put("/config")
def put_config(data: TeamConfigIn, db: Session = Depends(get_db), me: User = Manage) -> dict:
    cfg = team_access.save(db, data.rotate, data.lock_minutes)
    audit.log(db, me.id, "update", "team_access", None, {"rotate": cfg["rotate"], "lock_minutes": cfg["lock_minutes"]})
    db.commit()
    return {"rotate": cfg["rotate"], "lock_minutes": cfg["lock_minutes"]}


@router.get("/status", response_model=TeamStatus)
def status(request: Request, k: str | None = None, db: Session = Depends(get_db)) -> dict:
    """Is the code in the QR still valid? (The phone app asks before showing the login.)"""
    _check_key(db, request, k)
    return {"ok": True}


@router.get("/users", response_model=list[UserPublic])
def users(request: Request, k: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    _check_key(db, request, k)
    names = roles.names(db)
    return [
        {**UserPublic.model_validate(u).model_dump(), "locked": free_plan.is_locked(db, "users", u.id),
         "role_name": names.get(u.role, u.role)}
        for u in team_access.team_users(db)
    ]


@router.get("/lock")
def lock(db: Session = Depends(get_db), _: User = CurrentUser) -> dict:
    """Idle lock of the phone app, in minutes (separate from the register's `lock_minutes`)."""
    return {"lock_minutes": team_access.config(db)["lock_minutes"]}
