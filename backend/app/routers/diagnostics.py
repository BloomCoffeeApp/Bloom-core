"""«Enviar diagnóstico a soporte» (Configuración → Acerca de): admin only.

`GET /api/diagnostics/preview` returns exactly what would be sent; `POST /api/diagnostics/send` sends it
(only with `consent: true`) through the license-server client and returns the support code.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import AdminOnly
from app.db import get_db
from app.licensing import client as license_client
from app.models import User
from app.services import audit
from app.services import diagnostics as svc

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


class SendIn(BaseModel):
    consent: bool = False


@router.get("/preview")
def preview(db: Session = Depends(get_db), _: User = AdminOnly) -> dict:
    return svc.preview(db)


@router.post("/send")
def send(data: SendIn, db: Session = Depends(get_db), me: User = AdminOnly) -> dict:
    if not data.consent:
        raise HTTPException(400, "Falta tu consentimiento para enviar el diagnóstico.")
    ok, reason = svc.availability()
    if not ok:
        raise HTTPException(409, reason)
    try:
        code = svc.send(db)
    except license_client.LicenseServerError as e:
        if e.status is None:  # the server could not be reached
            raise HTTPException(503, str(e)) from e
        raise HTTPException(429 if e.status == 429 else 400, str(e)) from e
    audit.log(db, me.id, "send", "diagnostic", None, {"support_code": code})
    db.commit()
    return {"support_code": code}
