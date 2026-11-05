"""Pro marketing tools (their logic ships in the Pro edition; the tables live here so a single
Alembic history covers every edition):

- Loyalty stamp cards (`loyalty_pro`): "cada 15 compras, un café gratis".
- Promotions (`promos`): combos and scheduled discounts (happy hour).
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, utcnow


class LoyaltyProgram(IdMixin, TimestampMixin, Base):
    __tablename__ = "loyalty_programs"
    name: Mapped[str] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(default=True)
    starts_on: Mapped[date | None] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)
    # What earns a stamp: any|product|category|min_amount
    count_type: Mapped[str] = mapped_column(String(12), default="any")
    target_id: Mapped[int | None]  # product or category id (no FK: the program outlives a deletion)
    min_amount_cents: Mapped[int] = mapped_column(default=0)
    stamps_required: Mapped[int] = mapped_column(default=10)
    # Reward: product (optionally a size) given as a $0 line, or a pct|fixed discount on the sale.
    reward_type: Mapped[str] = mapped_column(String(10), default="product")
    reward_product_id: Mapped[int | None]
    reward_size_id: Mapped[int | None]
    reward_value: Mapped[int] = mapped_column(default=0)  # percent (pct) or cents (fixed)


class LoyaltyStamp(IdMixin, Base):
    """Stamp ledger: +N earned by a sale, -stamps_required on a redemption; voids reverse by sale_id."""

    __tablename__ = "loyalty_stamps"
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("loyalty_programs.id", ondelete="CASCADE"), index=True)
    stamps: Mapped[int]
    reason: Mapped[str] = mapped_column(String(120))
    sale_id: Mapped[int | None] = mapped_column(ForeignKey("sales.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Promo(IdMixin, TimestampMixin, Base):
    __tablename__ = "promos"
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(10), default="discount")  # discount|combo
    active: Mapped[bool] = mapped_column(default=True)
    starts_on: Mapped[date | None] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)
    weekdays: Mapped[list[int] | None] = mapped_column(JSON)  # 0 = Monday … 6 = Sunday; None = every day
    time_from: Mapped[str | None] = mapped_column(String(5))  # "HH:MM" local; window [from, to)
    time_to: Mapped[str | None] = mapped_column(String(5))
    # discount: pct|fixed (fixed = cents off per unit) on products or categories
    discount_type: Mapped[str] = mapped_column(String(6), default="pct")
    discount_value: Mapped[int] = mapped_column(default=0)
    target_type: Mapped[str] = mapped_column(String(10), default="product")  # product|category
    target_ids: Mapped[list[int] | None] = mapped_column(JSON)
    # combo: fixed price for the set [{product_id, size_id|None, qty}]
    combo_price_cents: Mapped[int] = mapped_column(default=0)
    combo_items: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
