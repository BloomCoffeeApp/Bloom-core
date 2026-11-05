"""Optional vendor account: link this installation (email → code) and choose which emails to receive.

Everything is proxied to the license server through app.licensing.client; nothing is stored in the
business database. Without a server (or offline) the app keeps working: the endpoints answer with
a clear message and the UI shows the switches disabled.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import AdminOnly
from app.db import get_db
from app.licensing import client as license_client
from app.models import User
from app.services import audit
from app.services import settings as settings_svc

router = APIRouter(prefix="/api/account", tags=["account"])
EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class LinkStartIn(BaseModel):
    email: str = Field(min_length=5, max_length=200, pattern=EMAIL)
    name: str | None = Field(default=None, max_length=80)
    accept_terms: bool = False
    marketing_opt_in: bool | None = None
    product_updates_opt_in: bool | None = None


class LinkConfirmIn(BaseModel):
    email: str = Field(min_length=5, max_length=200, pattern=EMAIL)
    code: str = Field(pattern=r"^\d{6}$")


class DeleteConfirmIn(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class PreferencesIn(BaseModel):
    news: bool | None = None
    updates: bool | None = None


def _info() -> dict:
    return {"linked": license_client.account_info() is not None, "account": license_client.account_info(),
            "server_configured": bool(license_client.server_url())}


def _call(fn, *args):
    try:
        return fn(*args)
    except license_client.LicenseServerError as e:
        raise HTTPException(400, str(e)) from e


@router.get("")
def get_account(_: User = AdminOnly) -> dict:
    return _info()


@router.post("/link/start")
def link_start(data: LinkStartIn, db: Session = Depends(get_db), _: User = AdminOnly) -> dict:
    if not data.accept_terms:
        raise HTTPException(400, "Tenés que aceptar los términos y la política de privacidad.")
    business = (settings_svc.get(db, "business") or {}).get("name")
    return _call(license_client.link_start, data.email, data.name, business, True,
                 data.marketing_opt_in, data.product_updates_opt_in)


@router.post("/link/confirm")
def link_confirm(data: LinkConfirmIn, me: User = AdminOnly, db: Session = Depends(get_db)) -> dict:
    result = _call(license_client.link_confirm, data.email, data.code)
    audit.log(db, me.id, "link", "account", None, {"email": (result.get("account") or {}).get("email"),
                                                     "trial": result.get("trial_status")})
    db.commit()
    return {**_info(), "trial_status": result.get("trial_status"), "trial_started": result.get("trial_started")}


@router.delete("")
def unlink(me: User = AdminOnly, db: Session = Depends(get_db)) -> dict:
    license_client.unlink_account()
    audit.log(db, me.id, "unlink", "account", None, None)
    db.commit()
    return _info()


@router.get("/preferences")
def get_preferences(_: User = AdminOnly) -> dict:
    """{available: false, reason} when there's no server, no connection or nothing to identify the customer."""
    if not license_client.server_url():
        return {"available": False, "reason": "Esta instalación no tiene servidor configurado: no hay mails para elegir."}
    try:
        return {"available": True, **license_client.email_preferences()}
    except license_client.LicenseServerError as e:
        return {"available": False, "reason": str(e)}


@router.put("/preferences")
def put_preferences(data: PreferencesIn, me: User = AdminOnly, db: Session = Depends(get_db)) -> dict:
    result = _call(license_client.update_email_preferences, data.news, data.updates)
    audit.log(db, me.id, "update", "email_preferences", None, data.model_dump(exclude_none=True))
    db.commit()
    return {"available": True, **result}


# ---------------------------------------------------------------- data rights (what the server keeps)


@router.post("/data/export")
def export_data(me: User = AdminOnly, db: Session = Depends(get_db)) -> dict:
    data = _call(license_client.export_account_data)
    audit.log(db, me.id, "export", "account_data", None, None)
    db.commit()
    return data


@router.post("/delete/start")
def delete_start(_: User = AdminOnly) -> dict:
    return _call(license_client.delete_account_start)


@router.post("/delete/confirm")
def delete_confirm(data: DeleteConfirmIn, me: User = AdminOnly, db: Session = Depends(get_db)) -> dict:
    result = _call(license_client.delete_account_confirm, data.code)
    audit.log(db, me.id, "delete", "account", None, None)
    db.commit()
    return {**_info(), "deleted": bool(result.get("deleted")), "retained": result.get("retained") or []}
