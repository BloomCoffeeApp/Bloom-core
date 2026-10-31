from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.db import get_db
from app.models import User
from app.schemas.reports import DashboardOut
from app.services import dashboard as svc

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    from_: date | None = Query(None, alias="from"),
    to: date | None = None,
    db: Session = Depends(get_db),
    user: User = CurrentUser,
) -> dict:
    a, b = svc.default_range(from_, to)
    if (b - a).days > 366:
        raise HTTPException(400, "El rango máximo es de un año")
    return svc.dashboard(db, a, b, svc.can_see_costs(user))
