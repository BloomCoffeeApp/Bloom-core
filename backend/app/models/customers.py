from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, utcnow


class Customer(IdMixin, TimestampMixin, Base):
    __tablename__ = "customers"
    name: Mapped[str] = mapped_column(String(120), index=True)
    phone: Mapped[str | None] = mapped_column(String(40), index=True)
    email: Mapped[str | None] = mapped_column(String(120))
    birthday: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    points: Mapped[int] = mapped_column(default=0)
    credit_limit_cents: Mapped[int] = mapped_column(default=0)
    # Positive balance = customer owes money (cuenta corriente).
    balance_cents: Mapped[int] = mapped_column(default=0)
    active: Mapped[bool] = mapped_column(default=True)


class LoyaltyTransaction(IdMixin, Base):
    __tablename__ = "loyalty_transactions"
    __table_args__ = (Index("ix_loyalty_transactions_customer_ts", "customer_id", "ts"),)  # migration 0007
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"))
    points: Mapped[int]
    reason: Mapped[str] = mapped_column(String(120))
    sale_id: Mapped[int | None] = mapped_column(ForeignKey("sales.id"))
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CustomerAccountMovement(IdMixin, Base):
    __tablename__ = "customer_account_movements"
    __table_args__ = (Index("ix_customer_account_movements_customer_ts", "customer_id", "ts"),)  # migration 0007
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"))
    amount_cents: Mapped[int]  # charge > 0, payment < 0
    type: Mapped[str] = mapped_column(String(10))  # charge|payment|void
    method: Mapped[str | None] = mapped_column(String(30))
    sale_id: Mapped[int | None] = mapped_column(ForeignKey("sales.id"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
