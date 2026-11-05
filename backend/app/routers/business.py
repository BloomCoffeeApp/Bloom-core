"""Business type (profile) and the modules it shows. Hiding is UI-level: every route keeps working."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import AdminOnly, CurrentUser
from app.db import get_db
from app.models import User
from app.services import audit
from app.services import business_profile as svc

router = APIRouter(prefix="/api/business", tags=["business"])


class ProfileIn(BaseModel):
    profile: str
    modules: dict[str, bool] = {}


class ModuleIn(BaseModel):
    enabled: bool


@router.get("/catalog")
def get_catalog() -> dict[str, Any]:
    """Profiles and modules (static, no business data): the setup wizard shows it before any login."""
    out = svc.info_for(svc.DEFAULT_PROFILE, {})
    return {"catalog": out["catalog"], "profiles": out["profiles"]}


@router.get("/modules")
def get_modules(db: Session = Depends(get_db), _: User = CurrentUser) -> dict[str, Any]:
    return svc.info(db)


@router.put("/profile")
def put_profile(data: ProfileIn, db: Session = Depends(get_db), me: User = AdminOnly) -> dict[str, Any]:
    try:
        svc.save(db, data.profile, data.modules)
    except svc.ProfileError as e:
        raise HTTPException(422, str(e)) from e
    out = svc.info(db)
    audit.log(db, me.id, "update", "setting", None,
              {"key": svc.SETTING, "profile": out["profile"], "overrides": out["overrides"]})
    db.commit()
    return out


@router.put("/modules/{module}")
def put_module(module: str, data: ModuleIn, db: Session = Depends(get_db), me: User = AdminOnly) -> dict[str, Any]:
    try:
        svc.set_module(db, module, data.enabled)
    except svc.ProfileError as e:
        raise HTTPException(422 if module in svc.MODULE_KEYS else 404, str(e)) from e
    audit.log(db, me.id, "update", "setting", None, {"key": svc.SETTING, "module": module, "enabled": data.enabled})
    db.commit()
    return svc.info(db)
