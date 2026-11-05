from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin, utcnow

CHANNELS = ("salon", "llevar", "delivery")


class PaymentMethod(IdMixin, Base):
    __tablename__ = "payment_methods"
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(60))
    active: Mapped[bool] = mapped_column(default=True)
    surcharge_pct: Mapped[float] = mapped_column(Float, default=0)
    sort_order: Mapped[int] = mapped_column(default=0)


class CashSession(IdMixin, Base):
    __tablename__ = "cash_sessions"
    opened_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    opening_cents: Mapped[int] = mapped_column(default=0)
    closed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="open")  # open|closed
    counts: Mapped[list["CashSessionCount"]] = relationship(cascade="all, delete-orphan")


class CashSessionCount(IdMixin, Base):
    __tablename__ = "cash_session_counts"
    session_id: Mapped[int] = mapped_column(ForeignKey("cash_sessions.id", ondelete="CASCADE"))
    payment_method: Mapped[str] = mapped_column(String(30))
    expected_cents: Mapped[int]
    counted_cents: Mapped[int]


class CashMovement(IdMixin, Base):
    __tablename__ = "cash_movements"
    session_id: Mapped[int] = mapped_column(ForeignKey("cash_sessions.id"))
    type: Mapped[str] = mapped_column(String(4))  # in|out
    amount_cents: Mapped[int]
    reason: Mapped[str] = mapped_column(String(200))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Sale(IdMixin, Base):
    __tablename__ = "sales"
    # Hot-query indexes (migration 0007, measured on 200k sales): completed/voided sales by date with
    # the totals the dashboard and reports add up (index-only scans), and a cash session's sales by
    # status. No ANALYZE stats in user DBs: SQLite picks the index with more leading equality columns,
    # so avoid adding (status, is_courtesy, …) indexes — they steal the cash-session queries.
    __table_args__ = (
        Index("ix_sales_status_ts", "status", "ts", "is_courtesy", "total_cents", "cost_cents"),
        Index("ix_sales_cash_session_status", "cash_session_id", "status"),
    )
    number: Mapped[int] = mapped_column(unique=True)
    cash_session_id: Mapped[int | None] = mapped_column(ForeignKey("cash_sessions.id"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), index=True)
    channel: Mapped[str] = mapped_column(String(10), default="salon")
    table_label: Mapped[str | None] = mapped_column(String(20))
    subtotal_cents: Mapped[int] = mapped_column(default=0)
    discount_cents: Mapped[int] = mapped_column(default=0)
    total_cents: Mapped[int] = mapped_column(default=0)
    cost_cents: Mapped[int] = mapped_column(default=0)
    points_earned: Mapped[int] = mapped_column(default=0)
    points_redeemed: Mapped[int] = mapped_column(default=0)
    # Pro `loyalty_pro`: a stamp-card discount reward applied to this sale (included in discount_cents).
    reward_program_id: Mapped[int | None]
    reward_discount_cents: Mapped[int] = mapped_column(default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(12), default="completed")  # completed|voided
    # Courtesy ("invita la casa"): stock moves as a normal sale but nothing is charged. Totals are 0 and
    # the menu value given away is kept in courtesy_cents; revenue/ticket aggregates exclude these sales.
    is_courtesy: Mapped[bool] = mapped_column(default=False, server_default=false())
    courtesy_cents: Mapped[int] = mapped_column(default=0, server_default="0")
    courtesy_reason: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    void_reason: Mapped[str | None] = mapped_column(Text)
    voided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    voided_at: Mapped[datetime | None] = mapped_column(DateTime)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    items: Mapped[list["SaleItem"]] = relationship(cascade="all, delete-orphan")
    payments: Mapped[list["SalePayment"]] = relationship(cascade="all, delete-orphan")


class SaleItem(IdMixin, Base):
    __tablename__ = "sale_items"
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), index=True)
    name_snapshot: Mapped[str] = mapped_column(String(160))
    # Size sold (snapshot): the id groups reports, the name survives renames/deletions.
    size_id: Mapped[int | None]
    size_name: Mapped[str | None] = mapped_column(String(60))
    qty: Mapped[float] = mapped_column(Float, default=1)
    unit_price_cents: Mapped[int]
    discount_cents: Mapped[int] = mapped_column(default=0)
    total_cents: Mapped[int] = mapped_column(default=0)
    cost_cents: Mapped[int] = mapped_column(default=0)
    modifiers: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(String(200))
    # Pro `promos` (snapshot): the promotion applied and its part of discount_cents.
    promo_id: Mapped[int | None]
    promo_name: Mapped[str | None] = mapped_column(String(120))
    promo_discount_cents: Mapped[int] = mapped_column(default=0, server_default="0")
    # Pro `loyalty_pro`: free product given as a stamp-card reward ($0 line, stock moves).
    reward_program_id: Mapped[int | None]
    courtesy_reason: Mapped[str | None] = mapped_column(String(60))


class SalePayment(IdMixin, Base):
    __tablename__ = "sale_payments"
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id", ondelete="CASCADE"), index=True)
    method: Mapped[str] = mapped_column(String(30))
    amount_cents: Mapped[int]
    tendered_cents: Mapped[int | None]
    change_cents: Mapped[int] = mapped_column(default=0)


class Expense(IdMixin, TimestampMixin, Base):
    """General business expenses (rent, utilities) for reports."""

    __tablename__ = "expenses"
    category: Mapped[str] = mapped_column(String(60))
    description: Mapped[str | None] = mapped_column(String(200))
    amount_cents: Mapped[int]
    date: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
