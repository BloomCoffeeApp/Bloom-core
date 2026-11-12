from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, create_session, hash_pin, login_throttle, verify_pin
from app.db import get_db
from app.models import User, UserSession
from app.schemas.common import Ok
from app.schemas.users import LoginIn, LoginOut, SetupIn, UserMe, UserPublic
from app.services import audit, business_profile, free_plan, roles, settings

router = APIRouter(prefix="/api", tags=["auth"])


@router.get("/setup/status")
def setup_status(db: Session = Depends(get_db)) -> dict:
    has_users = (db.scalar(select(func.count(User.id))) or 0) > 0
    return {"needs_setup": not has_users, "business": settings.get(db, "business")}


@router.post("/setup", response_model=LoginOut)
def setup(data: SetupIn, db: Session = Depends(get_db)) -> LoginOut:
    if db.scalar(select(func.count(User.id))):
        raise HTTPException(400, "La app ya está configurada")
    admin = User(name=data.admin_name, pin_hash=hash_pin(data.admin_pin), role="admin", color="amber")
    db.add(admin)
    biz = settings.get(db, "business")
    settings.put(db, "business", {**biz, "name": data.business_name})
    settings.put(db, "setup_done", True)
    if data.profile is not None:
        try:
            business_profile.save(db, data.profile, data.modules)
        except business_profile.ProfileError as e:
            raise HTTPException(422, str(e)) from e
    db.flush()
    from app.seed import seed_base, seed_demo

    if data.load_demo:
        seed_demo(db, admin_id=admin.id)
    else:
        seed_base(db)
    db.commit()
    return LoginOut(token=create_session(db, admin), user=me_out(db, admin))


@router.get("/auth/users", response_model=list[UserPublic])
def login_users(db: Session = Depends(get_db)) -> list[dict]:
    names = roles.names(db)
    return [
        {**UserPublic.model_validate(u).model_dump(), "locked": free_plan.is_locked(db, "users", u.id),
         "role_name": names.get(u.role, u.role)}
        for u in db.scalars(select(User).where(User.active.is_(True)).order_by(User.name))
    ]


@router.post("/auth/login", response_model=LoginOut)
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)) -> LoginOut:
    keys = (f"user:{data.user_id}", f"ip:{request.client.host if request.client else '?'}")
    if wait := login_throttle.wait_seconds(*keys):
        raise HTTPException(429, f"Demasiados intentos fallidos. Probá de nuevo en {wait} segundos.")
    user = db.get(User, data.user_id)
    if not user or not user.active or not verify_pin(user.pin_hash, data.pin):
        login_throttle.fail(*keys)
        audit.log(db, user.id if user else None, "login_failed", "user", data.user_id)
        db.commit()
        raise HTTPException(401, "PIN incorrecto")
    free_plan.ensure_usable(db, "users", user.id, user.name)
    login_throttle.success(*keys)
    audit.log(db, user.id, "login", "user", user.id)
    return LoginOut(token=create_session(db, user), user=me_out(db, user))


@router.post("/auth/logout", response_model=Ok)
def logout(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> Ok:
    if authorization:
        token = authorization.removeprefix("Bearer ").strip()
        db.execute(delete(UserSession).where(UserSession.token == token))
        db.commit()
    return Ok()


@router.get("/auth/me", response_model=UserMe)
def me(user: User = CurrentUser, db: Session = Depends(get_db)) -> dict:
    return me_out(db, user)


def me_out(db: Session, user: User) -> dict:
    return {**UserPublic.model_validate(user).model_dump(), "role_name": roles.role_name(db, user.role),
            "permissions": sorted(roles.permissions_of(user))}
