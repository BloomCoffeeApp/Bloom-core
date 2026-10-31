from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin, utcnow

UNITS = ("g", "ml", "u")
MOVEMENT_TYPES = ("purchase", "sale", "adjustment", "waste", "internal", "void", "count")


class StockCategory(IdMixin, TimestampMixin, Base):
    __tablename__ = "stock_categories"
    name: Mapped[str] = mapped_column(String(80))


class StockItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "stock_items"
    category_id: Mapped[int | None] = mapped_column(ForeignKey("stock_categories.id"))
    name: Mapped[str] = mapped_column(String(120))
    unit: Mapped[str] = mapped_column(String(4), default="u")
    current_qty: Mapped[float] = mapped_column(Float, default=0)
    min_qty: Mapped[float] = mapped_column(Float, default=0)
    # Cost per base unit, in cents, as float to keep precision for g/ml.
    avg_cost_cents: Mapped[float] = mapped_column(Float, default=0)
    default_supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"))
    track_expiry: Mapped[bool] = mapped_column(default=False)
    active: Mapped[bool] = mapped_column(default=True)


class StockLot(IdMixin, Base):
    __tablename__ = "stock_lots"
    stock_item_id: Mapped[int] = mapped_column(ForeignKey("stock_items.id", ondelete="CASCADE"))
    qty_remaining: Mapped[float] = mapped_column(Float)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    purchase_item_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_items.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class StockMovement(IdMixin, Base):
    __tablename__ = "stock_movements"
    stock_item_id: Mapped[int] = mapped_column(ForeignKey("stock_items.id"), index=True)
    type: Mapped[str] = mapped_column(String(20))
    qty: Mapped[float] = mapped_column(Float)  # signed
    unit_cost_cents: Mapped[float] = mapped_column(Float, default=0)
    balance_after: Mapped[float] = mapped_column(Float, default=0)
    ref_type: Mapped[str | None] = mapped_column(String(30))
    ref_id: Mapped[int | None]
    reason: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class InventoryCount(IdMixin, TimestampMixin, Base):
    __tablename__ = "inventory_counts"
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|applied|cancelled
    notes: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    items: Mapped[list["InventoryCountItem"]] = relationship(cascade="all, delete-orphan")


class InventoryCountItem(IdMixin, Base):
    __tablename__ = "inventory_count_items"
    count_id: Mapped[int] = mapped_column(ForeignKey("inventory_counts.id", ondelete="CASCADE"))
    stock_item_id: Mapped[int] = mapped_column(ForeignKey("stock_items.id"))
    expected_qty: Mapped[float] = mapped_column(Float)
    counted_qty: Mapped[float | None] = mapped_column(Float)
