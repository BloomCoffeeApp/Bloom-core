"""Roles editor (admin only): permission catalog, built-in and custom roles."""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import AdminOnly, CurrentUser
from app.db import get_db
from app.models import User
from app.schemas.common import Ok
from app.services import roles

router = APIRouter(prefix="/api/roles", tags=["roles"])


class RoleIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    permissions: list[str] = []


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    permissions: list[str] | None = None


@router.get("/catalog")
def permission_catalog(_: User = CurrentUser) -> list[dict[str, Any]]:
    return roles.catalog()


@router.get("")
def list_roles(db: Session = Depends(get_db), _: User = CurrentUser) -> list[dict[str, Any]]:
    # Any user may read the list (names for badges); only admins change it.
    return roles.list_roles(db)


@router.post("")
def create_role(data: RoleIn, db: Session = Depends(get_db), me: User = AdminOnly) -> dict[str, Any]:
    return roles.create(db, data.name, data.permissions, me)


@router.patch("/{key}")
def update_role(key: str, data: RoleUpdate, db: Session = Depends(get_db), me: User = AdminOnly) -> dict[str, Any]:
    return roles.update(db, key, data.name, data.permissions, me)


@router.post("/{key}/reset")
def reset_role(key: str, db: Session = Depends(get_db), me: User = AdminOnly) -> dict[str, Any]:
    return roles.reset(db, key, me)


@router.delete("/{key}", response_model=Ok)
def delete_role(key: str, db: Session = Depends(get_db), me: User = AdminOnly) -> Ok:
    roles.delete(db, key, me)
    return Ok()
