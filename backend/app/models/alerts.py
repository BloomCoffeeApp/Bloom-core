from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin, utcnow


class Alert(IdMixin, Base):
    __tablename__ = "alerts"
    type: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(10), default="info")  # info|warning|critical
    title: Mapped[str] = mapped_column(String(160))
    message: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(200))
    entity: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[int | None]
    dedupe_key: Mapped[str] = mapped_column(String(120), unique=True)
    status: Mapped[str] = mapped_column(String(10), default="open")  # open|read|resolved
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)


class Notice(IdMixin, TimestampMixin, Base):
    __tablename__ = "notices"
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str | None] = mapped_column(Text)
    pinned: Mapped[bool] = mapped_column(default=False)
    color: Mapped[str] = mapped_column(String(20), default="amber")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)


class Checklist(IdMixin, TimestampMixin, Base):
    __tablename__ = "checklists"
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(10), default="custom")  # opening|closing|custom
    active: Mapped[bool] = mapped_column(default=True)
    items: Mapped[list["ChecklistItem"]] = relationship(
        cascade="all, delete-orphan", order_by="ChecklistItem.sort_order"
    )


class ChecklistItem(IdMixin, Base):
    __tablename__ = "checklist_items"
    checklist_id: Mapped[int] = mapped_column(ForeignKey("checklists.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(String(200))
    sort_order: Mapped[int] = mapped_column(default=0)


class ChecklistRun(IdMixin, Base):
    __tablename__ = "checklist_runs"
    checklist_id: Mapped[int] = mapped_column(ForeignKey("checklists.id", ondelete="CASCADE"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    items: Mapped[list["ChecklistRunItem"]] = relationship(cascade="all, delete-orphan")


class ChecklistRunItem(IdMixin, Base):
    __tablename__ = "checklist_run_items"
    run_id: Mapped[int] = mapped_column(ForeignKey("checklist_runs.id", ondelete="CASCADE"))
    item_id: Mapped[int] = mapped_column(ForeignKey("checklist_items.id", ondelete="CASCADE"))
    done: Mapped[bool] = mapped_column(default=False)
    done_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    done_at: Mapped[datetime | None] = mapped_column(DateTime)
