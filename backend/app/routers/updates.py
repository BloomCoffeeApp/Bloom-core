from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import AdminOnly
from app.db import get_db
from app.models import User
from app.schemas.updates import UpdateStatus
from app.services import audit
from app.services import updates as svc

router = APIRouter(prefix="/api/updates", tags=["updates"])


@router.get("", response_model=UpdateStatus)
def get_status(_: User = AdminOnly) -> dict:
    return svc.status()


@router.post("/check", response_model=UpdateStatus)
def check(_: User = AdminOnly) -> dict:
    return svc.check()


@router.post("/install", response_model=UpdateStatus)
def install(db: Session = Depends(get_db), me: User = AdminOnly) -> dict:
    try:
        result = svc.start_install()
    except svc.UpdateError as e:
        raise HTTPException(409, str(e)) from e
    version = result["latest"]["version"] if result["latest"] else None
    audit.log(db, me.id, "update", "app", None, {"from": result["current_version"], "to": version})
    db.commit()
    return result
