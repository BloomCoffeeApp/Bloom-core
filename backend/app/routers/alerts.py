from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, Manager
from app.db import get_db
from app.models import Alert, Checklist, User, utcnow
from app.schemas.alerts import (
    AlertOut,
    AlertSummary,
    ChecklistIn,
    ChecklistOut,
    ChecklistRunOut,
    ChecklistUpdate,
    NoticeIn,
    NoticeOut,
    NoticeUpdate,
    RunItemPatch,
)
from app.schemas.common import Ok
from app.services import alerts_engine
from app.services import notices as nsvc

router = APIRouter(prefix="/api", tags=["alerts"])

# ---------------------------------------------------------------- alerts

_SEVERITY_ORDER = case({"critical": 0, "warning": 1}, value=Alert.severity, else_=2)


def _summary(db: Session) -> dict[str, int]:
    rows = db.execute(
        select(Alert.status, Alert.severity, func.count(Alert.id))
        .where(Alert.status != "resolved")
        .group_by(Alert.status, Alert.severity)
    ).all()
    out = {"open": 0, "critical": 0, "read": 0, "warning": 0, "info": 0}
    for status, severity, n in rows:
        if status == "open":
            out["open"] += n
            if severity in ("critical", "warning", "info"):
                out[severity] += n
        elif status == "read":
            out["read"] += n
    return out


def _get_alert(db: Session, alert_id: int) -> Alert:
    a = db.get(Alert, alert_id)
    if a is None:
        raise HTTPException(404, "Alerta no encontrada")
    return a


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(
    status: str = Query(default="active", pattern=r"^(open|read|resolved|active|all)$"),
    limit: int = Query(default=300, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = CurrentUser,
) -> list[Alert]:
    """status: open | read | resolved | active (open+read) | all."""
    stmt = select(Alert)
    if status == "active":
        stmt = stmt.where(Alert.status != "resolved")
    elif status != "all":
        stmt = stmt.where(Alert.status == status)
    if status == "resolved":
        stmt = stmt.order_by(Alert.resolved_at.desc().nulls_last(), Alert.id.desc())
    else:
        stmt = stmt.order_by(_SEVERITY_ORDER, Alert.created_at.desc(), Alert.id.desc())
    return list(db.scalars(stmt.limit(limit)))


@router.get("/alerts/summary", response_model=AlertSummary)
def alerts_summary(db: Session = Depends(get_db), _: User = CurrentUser) -> dict[str, int]:
    return _summary(db)


@router.post("/alerts/read-all", response_model=AlertSummary)
def read_all(db: Session = Depends(get_db), _: User = CurrentUser) -> dict[str, int]:
    for a in db.scalars(select(Alert).where(Alert.status == "open")):
        a.status = "read"
    db.commit()
    return _summary(db)


@router.post("/alerts/refresh", response_model=AlertSummary)
def refresh_alerts(db: Session = Depends(get_db), _: User = CurrentUser) -> dict[str, int]:
    alerts_engine.evaluate(db)
    db.commit()
    return _summary(db)


@router.post("/alerts/{alert_id}/read", response_model=AlertOut)
def read_alert(alert_id: int, db: Session = Depends(get_db), _: User = CurrentUser) -> Alert:
    a = _get_alert(db, alert_id)
    if a.status == "open":
        a.status = "read"
        db.commit()
        db.refresh(a)
    return a


@router.post("/alerts/{alert_id}/resolve", response_model=AlertOut)
def resolve_alert(alert_id: int, db: Session = Depends(get_db), _: User = CurrentUser) -> Alert:
    a = _get_alert(db, alert_id)
    if a.status != "resolved":
        a.status = "resolved"
        a.resolved_at = utcnow()
        db.commit()
        db.refresh(a)
    return a


# ---------------------------------------------------------------- notices


@router.get("/notices", response_model=list[NoticeOut])
def list_notices(
    include_expired: bool = False, db: Session = Depends(get_db), user: User = CurrentUser
) -> list[dict[str, Any]]:
    can_see_expired = user.role in ("admin", "encargado")
    return nsvc.list_notices(db, include_expired and can_see_expired)


@router.post("/notices", response_model=NoticeOut)
def create_notice(data: NoticeIn, db: Session = Depends(get_db), user: User = Manager) -> dict[str, Any]:
    return nsvc.create_notice(db, data.model_dump(), user)


@router.patch("/notices/{notice_id}", response_model=NoticeOut)
def update_notice(
    notice_id: int, data: NoticeUpdate, db: Session = Depends(get_db), user: User = Manager
) -> dict[str, Any]:
    n = nsvc.get_notice(db, notice_id)
    return nsvc.update_notice(db, n, data.model_dump(exclude_unset=True), user)


@router.delete("/notices/{notice_id}", response_model=Ok)
def delete_notice(notice_id: int, db: Session = Depends(get_db), user: User = Manager) -> Ok:
    nsvc.delete_notice(db, nsvc.get_notice(db, notice_id), user)
    return Ok()


# ---------------------------------------------------------------- checklists


@router.get("/checklists", response_model=list[ChecklistOut])
def list_checklists(db: Session = Depends(get_db), _: User = CurrentUser) -> list[Checklist]:
    return nsvc.list_checklists(db)


@router.get("/checklists/today", response_model=list[ChecklistRunOut])
def checklists_today(db: Session = Depends(get_db), _: User = CurrentUser) -> list[dict[str, Any]]:
    return nsvc.today(db)


@router.post("/checklists", response_model=ChecklistOut)
def create_checklist(data: ChecklistIn, db: Session = Depends(get_db), user: User = Manager) -> Checklist:
    return nsvc.create_checklist(db, data.model_dump(), user)


@router.patch("/checklists/{checklist_id}", response_model=ChecklistOut)
def update_checklist(
    checklist_id: int, data: ChecklistUpdate, db: Session = Depends(get_db), user: User = Manager
) -> Checklist:
    c = nsvc.get_checklist(db, checklist_id)
    return nsvc.update_checklist(db, c, data.model_dump(exclude_unset=True), user)


@router.delete("/checklists/{checklist_id}", response_model=Ok)
def delete_checklist(checklist_id: int, db: Session = Depends(get_db), user: User = Manager) -> Ok:
    """Deactivates the checklist (keeps the history of runs)."""
    c = nsvc.get_checklist(db, checklist_id)
    nsvc.update_checklist(db, c, {"active": False}, user)
    return Ok()


@router.post("/checklists/{checklist_id}/runs", response_model=ChecklistRunOut)
def start_run(checklist_id: int, db: Session = Depends(get_db), user: User = CurrentUser) -> dict[str, Any]:
    c = nsvc.get_checklist(db, checklist_id)
    run = nsvc.start_run(db, c, user)
    return nsvc.run_out(db, c, run, nsvc.user_names(db))


@router.patch("/checklist-runs/{run_id}/items/{item_id}", response_model=ChecklistRunOut)
def toggle_run_item(
    run_id: int, item_id: int, data: RunItemPatch, db: Session = Depends(get_db), user: User = CurrentUser
) -> dict[str, Any]:
    """item_id is the checklist item id (ChecklistItem.id)."""
    run = nsvc.toggle_run_item(db, run_id, item_id, data.done, user)
    c = nsvc.get_checklist(db, run.checklist_id)
    return nsvc.run_out(db, c, run, nsvc.user_names(db))
