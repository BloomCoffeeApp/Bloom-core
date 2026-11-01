from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import AdminOnly, CurrentUser
from app.config import APP_DISPLAY_NAME
from app.db import get_db
from app.licensing import PRO_FEATURES, current_status, free_limits
from app.licensing import client as license_client
from app.licensing.features import PRO_LABEL
from app.licensing.status import store_token
from app.models import User
from app.services import audit
from app.services import settings as settings_svc

router = APIRouter(prefix="/api/license", tags=["license"])


class KeyIn(BaseModel):
    key: str = Field(min_length=8, max_length=64)


class CheckoutIn(BaseModel):
    plan: str = Field(min_length=2, max_length=40)
    email: str = Field(min_length=5, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class TokenIn(BaseModel):
    token: str = Field(min_length=20, max_length=4096)


def _out(status=None) -> dict:
    s = status or current_status()
    return {
        **s.as_dict(),
        "pro_label": PRO_LABEL,
        "app_name": APP_DISPLAY_NAME,
        "catalog": PRO_FEATURES,
        "free_limits": free_limits(),
        "server_configured": bool(license_client.server_url()),
        "pending_checkout": license_client.pending_checkout_id(),
        "pending_price_change": license_client.pending_price_change() if s.valid else None,
    }


def _server_call(fn, *args) -> dict:
    try:
        return _out(fn(*args))
    except license_client.LicenseServerError as e:
        raise HTTPException(400, str(e)) from e


@router.get("")
def get_license(_: User = CurrentUser) -> dict:
    return _out()


@router.post("/activate")
def activate(data: KeyIn, _: User = AdminOnly) -> dict:
    return _server_call(license_client.activate, data.key)


@router.post("/trial")
def trial(_: User = AdminOnly) -> dict:
    return _server_call(license_client.start_trial)


@router.post("/refresh")
def refresh(_: User = AdminOnly) -> dict:
    return _server_call(license_client.refresh)


@router.post("/import")
def import_license(data: TokenIn, _: User = AdminOnly) -> dict:
    """Offline activation: a license file issued for this computer's id."""
    status = store_token(data.token)
    if status.problem:
        store_token(None)
        raise HTTPException(400, status.problem)
    return _out(status)


@router.delete("")
def deactivate(_: User = AdminOnly) -> dict:
    return _out(license_client.deactivate())


@router.get("/plans")
def plans(_: User = AdminOnly) -> dict:
    try:
        return license_client.plans()
    except license_client.LicenseServerError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/checkout")
def start_checkout(data: CheckoutIn, db: Session = Depends(get_db), _: User = AdminOnly) -> dict:
    business = (settings_svc.get(db, "business") or {}).get("name")
    try:
        return license_client.start_checkout(data.plan, data.email, business)
    except license_client.LicenseServerError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/checkout/{checkout_id}")
def checkout_status(checkout_id: str, _: User = AdminOnly) -> dict:
    try:
        result = license_client.checkout_status(checkout_id)
    except license_client.LicenseServerError as e:
        raise HTTPException(400, str(e)) from e
    if result.get("license"):
        result["license"] = _out()  # same shape as GET /api/license (the UI caches it as such)
    return result


@router.get("/subscription")
def subscription(_: User = AdminOnly) -> dict:
    try:
        return license_client.subscription()
    except license_client.LicenseServerError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/subscription/accept-price")
def accept_price(me: User = AdminOnly, db: Session = Depends(get_db)) -> dict:
    """Accepts the new price of the subscription announced by the vendor."""
    try:
        result = license_client.accept_price()
    except license_client.LicenseServerError as e:
        raise HTTPException(400, str(e)) from e
    change = result.get("pending_price_change") or {}
    audit.log(db, me.id, "accept_price", "subscription", None,
              {"new_amount_cents": change.get("new_amount_cents"), "effective_at": change.get("effective_at")})
    db.commit()
    return result


@router.post("/subscription/cancel")
def cancel_subscription(me: User = AdminOnly, db: Session = Depends(get_db)) -> dict:
    try:
        result = license_client.cancel_subscription()
    except license_client.LicenseServerError as e:
        raise HTTPException(400, str(e)) from e
    audit.log(db, me.id, "cancel", "subscription", None, {"code": result.get("cancellation_code")})
    db.commit()
    return result
