from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORM


class AlertOut(ORM):
    id: int
    type: str
    severity: str
    title: str
    message: str | None
    link: str | None
    entity: str | None
    entity_id: int | None
    status: str
    created_at: datetime
    resolved_at: datetime | None


class AlertSummary(BaseModel):
    open: int
    critical: int
    read: int = 0
    warning: int = 0
    info: int = 0


# ---------------------------------------------------------------- notices

NOTICE_COLORS = r"^(amber|rose|sky|emerald|violet|stone)$"


class NoticeIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    body: str | None = None
    pinned: bool = False
    color: str = Field(default="amber", pattern=NOTICE_COLORS)
    expires_at: datetime | None = None


class NoticeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    body: str | None = None
    pinned: bool | None = None
    color: str | None = Field(default=None, pattern=NOTICE_COLORS)
    expires_at: datetime | None = None


class NoticeOut(BaseModel):
    id: int
    title: str
    body: str | None
    pinned: bool
    color: str
    expires_at: datetime | None
    author_id: int | None
    author_name: str | None
    created_at: datetime
    updated_at: datetime
    expired: bool


# ---------------------------------------------------------------- checklists

CHECKLIST_KIND = r"^(opening|closing|custom)$"


class ChecklistItemIn(BaseModel):
    id: int | None = None
    text: str = Field(min_length=1, max_length=200)


class ChecklistIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = Field(default="custom", pattern=CHECKLIST_KIND)
    items: list[ChecklistItemIn] = []


class ChecklistUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    kind: str | None = Field(default=None, pattern=CHECKLIST_KIND)
    active: bool | None = None
    items: list[ChecklistItemIn] | None = None


class ChecklistItemOut(ORM):
    id: int
    text: str
    sort_order: int


class ChecklistOut(ORM):
    id: int
    name: str
    kind: str
    active: bool
    items: list[ChecklistItemOut]


class RunItemOut(BaseModel):
    item_id: int
    text: str
    done: bool
    done_by: int | None
    done_by_name: str | None
    done_at: datetime | None


class ChecklistRunOut(BaseModel):
    checklist_id: int
    name: str
    kind: str
    run_id: int | None
    started_at: datetime | None
    started_by_name: str | None
    completed_at: datetime | None
    done: int
    total: int
    items: list[RunItemOut]


class RunItemPatch(BaseModel):
    done: bool


# ---------------------------------------------------------------- notifications (bell popup)


class UrgentItem(BaseModel):
    key: str
    kind: str  # online_order | table_order | call_waiter | call_bill
    title: str
    detail: str | None = None
    at: datetime
    to: str


class UrgentOut(BaseModel):
    items: list[UrgentItem]
    total: int
