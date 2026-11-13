from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class IdempotencyKey(Base):
    """A client-chosen key for ONE money-moving request (sale, cash movement, account payment): sending it again
    returns the resource it created instead of creating another. The row is written in the same transaction as the
    resource. `body_hash` catches a key reused with a different request. Old rows are pruned (services/idempotency)."""

    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    scope: Mapped[str] = mapped_column(String(30))
    user_id: Mapped[int | None]
    body_hash: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
