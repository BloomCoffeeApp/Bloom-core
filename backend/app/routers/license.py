from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.auth import AdminOnly, CurrentUser
from app.config import APP_DISPLAY_NAME
from app.licensing import FREE_MAX_USERS, PRO_FEATURES, current_status
from app.licensing import client as license_client
from app.licensing.features import PRO_LABEL
from app.licensing.status import store_token
from app.models import User

router = APIRouter(prefix="/api/license", tags=["license"])


class KeyIn(BaseModel):
    key: str = Field(min_length=8, max_length=64)


class TokenIn(BaseModel):
    token: str = Field(min_length=20, max_length=4096)


def _out(status=None) -> dict:
    s = status or current_status()
    return {
        **s.as_dict(),
        "pro_label": PRO_LABEL,
        "app_name": APP_DISPLAY_NAME,
        "catalog": PRO_FEATURES,
        "free_max_users": FREE_MAX_USERS,
        "server_configured": bool(license_client.server_url()),
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
