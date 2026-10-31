"""In-app update status (Configuración → Acerca de)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class UpdateInfo(BaseModel):
    version: str
    notes: str
    published_at: str
    size: int


class UpdateProgress(BaseModel):
    downloaded: int
    total: int


class UpdateStatus(BaseModel):
    current_version: str
    configured: bool
    state: Literal["idle", "checking", "downloading", "verifying", "installing", "ready", "error"]
    available: bool
    latest: UpdateInfo | None
    checked_at: datetime | None
    error: str | None
    message: str | None
    progress: UpdateProgress
    can_install: bool
