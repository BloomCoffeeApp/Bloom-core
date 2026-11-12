from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import lan
from app.auth import CurrentUser, Perm, hash_pin, revoke_sessions
from app.db import get_db
from app.licensing import has_feature
from app.licensing.features import PRO_LABEL
from app.models import User
from app.schemas.users import UserCreate, UserOut, UserUpdate
from app.services import audit, business_profile, free_plan, roles
from app.services import settings as settings_svc

router = APIRouter(prefix="/api", tags=["users"])
UsersAdmin = Perm("users.manage")
SettingsAdmin = Perm("settings.manage")


def user_out(db: Session, u: User) -> dict[str, Any]:
    return {**UserOut.model_validate(u).model_dump(), "locked": u.active and free_plan.is_locked(db, "users", u.id),
            "role_name": roles.role_name(db, u.role)}


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = UsersAdmin) -> list[dict[str, Any]]:
    return [user_out(db, u) for u in db.scalars(select(User).order_by(User.name))]


@router.post("/users", response_model=UserOut)
def create_user(data: UserCreate, db: Session = Depends(get_db), me: User = UsersAdmin) -> dict[str, Any]:
    roles.check_can_assign(db, me, data.role)
    free_plan.check_can_create(db, "users")
    user = User(name=data.name, pin_hash=hash_pin(data.pin), role=data.role, color=data.color)
    db.add(user)
    db.flush()
    free_plan.on_created(db, "users", user.id)
    audit.log(db, me.id, "create", "user", user.id, {"name": user.name, "role": user.role})
    db.commit()
    return user_out(db, user)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db), me: User = UsersAdmin) -> dict[str, Any]:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "Usuario no encontrado")
    changes = data.model_dump(exclude_unset=True)
    roles.check_can_assign(db, me, changes.get("role") or user.role, target=user)
    if changes.get("active") is False and user.active:
        free_plan.on_archived(db, "users", user.id)
    elif changes.get("active") is True and not user.active:
        free_plan.on_reactivated(db, "users", user.id)
    elif user.active and set(changes) - {"active"}:
        free_plan.ensure_usable(db, "users", user.id, user.name)
    demoting = changes.get("active") is False or changes.get("role", "admin") != "admin"
    if demoting and user.role == "admin":
        admins = db.scalar(select(func.count(User.id)).where(User.role == "admin", User.active.is_(True)))
        if (admins or 0) <= 1:
            raise HTTPException(400, "Tiene que quedar al menos un administrador activo")
    pin = changes.pop("pin", None)
    if pin:
        user.pin_hash = hash_pin(pin)
    security_change = bool(pin) or changes.get("active") is False or (
        "role" in changes and changes["role"] != user.role
    )
    for k, v in changes.items():
        setattr(user, k, v)
    if security_change and user.id != me.id:
        revoke_sessions(db, user.id)
    audit.log(db, me.id, "update", "user", user.id, changes)
    db.commit()
    free_plan.invalidate()
    return user_out(db, user)


@router.get("/settings")
def get_settings(db: Session = Depends(get_db), _: User = CurrentUser) -> dict[str, Any]:
    return settings_svc.get_all(db)


@router.put("/settings/{key}")
def put_setting(
    key: str, value: Any = Body(...), db: Session = Depends(get_db), me: User = SettingsAdmin
) -> dict[str, Any]:
    if key not in settings_svc.DEFAULTS or key in (free_plan.SETTING, business_profile.SETTING):
        raise HTTPException(404, "Configuración inexistente")
    if key == "network" and isinstance(value, dict) and value.get("lan_enabled") and not has_feature("lan"):
        raise HTTPException(402, f"El modo red local es parte de {PRO_LABEL}.")
    settings_svc.put(db, key, value)
    audit.log(db, me.id, "update", "setting", None, {"key": key})
    db.commit()
    if key == "network":
        lan.apply(bool(isinstance(value, dict) and value.get("lan_enabled")))
    return {"key": key, "value": settings_svc.get(db, key)}
