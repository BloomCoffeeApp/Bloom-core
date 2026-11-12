from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.auth import CurrentUser, Perm
from app.licensing import require_feature
from app.db import get_db
from app.models import User
from app.schemas.reports import AuditRow, BackupOut, RestoreIn, RestoreOut, SystemInfo
from app.services import audit
from app.schemas.third_party import ThirdPartyNotices
from app.services import system as svc
from app.services import third_party

AdminOnly = Perm("system.manage")
router = APIRouter(prefix="/api", tags=["system"])


@router.get("/system/info", response_model=SystemInfo)
def system_info(db: Session = Depends(get_db), _: User = AdminOnly) -> dict:
    return svc.info(db)


@router.get("/system/third-party-licenses", response_model=ThirdPartyNotices)
def third_party_licenses(_: User = CurrentUser) -> dict:
    return third_party.notices()


@router.get("/system/backups", response_model=list[BackupOut])
def list_backups(_: User = AdminOnly) -> list[dict]:
    return svc.list_backups()


@router.post("/system/backups", response_model=BackupOut)
def create_backup(db: Session = Depends(get_db), me: User = AdminOnly) -> dict:
    info = svc.create_backup(db, "manual")
    audit.log(db, me.id, "create", "backup", None, {"name": info["name"]})
    db.commit()
    return info


@router.get("/system/backups/{name}/download", dependencies=[Depends(require_feature("backup_export"))])
def download_backup(name: str, _: User = AdminOnly) -> FileResponse:
    path = svc.resolve_backup(name)
    if path is None:
        raise HTTPException(404, "Respaldo no encontrado")
    return FileResponse(path, media_type="application/octet-stream", filename=path.name)


@router.post("/system/restore", response_model=RestoreOut)
def restore(data: RestoreIn, db: Session = Depends(get_db), me: User = AdminOnly) -> dict:
    path = svc.resolve_backup(data.name)
    if path is None:
        raise HTTPException(400, "Respaldo inválido: elegí uno de la lista")
    user_id, user_name = me.id, me.name
    db.rollback()  # release this session's read transaction before overwriting the DB
    db.close()
    try:
        safety = svc.restore_backup(path)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    try:  # best effort: the user may not exist in the restored DB
        audit.log(db, None, "restore", "backup", None, {"name": path.name, "by": user_name, "by_id": user_id})
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
    return {
        "restored": path.name,
        "safety_backup": safety,
        "message": "Respaldo restaurado. Cerrá y volvé a abrir la aplicación para continuar.",
    }


@router.get("/system/lan-qr", dependencies=[Depends(require_feature("lan"))])
def lan_qr(_: User = Perm("settings.manage")) -> Response:
    url = svc.lan_url()
    if not url:
        raise HTTPException(404, "No se encontró una red local")
    return Response(content=svc.qr_png(url), media_type="image/png", headers={"Cache-Control": "no-store"})


@router.get("/system/menu-qr", dependencies=[Depends(require_feature("public_menu"))])
def menu_qr(_: User = Perm("settings.manage")) -> Response:
    url = svc.menu_url()
    if not url:
        raise HTTPException(404, "No se encontró una red local")
    return Response(content=svc.qr_png(url), media_type="image/png", headers={"Cache-Control": "no-store"})


@router.get("/system/audit", response_model=list[AuditRow])
def audit_log(limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db), _: User = AdminOnly) -> list[dict]:
    return svc.audit_rows(db, limit)
