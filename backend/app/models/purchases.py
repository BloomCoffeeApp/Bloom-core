from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin, utcnow


class Supplier(IdMixin, TimestampMixin, Base):
    __tablename__ = "suppliers"
    name: Mapped[str] = mapped_column(String(120))
    cuit: Mapped[str | None] = mapped_column(String(20))
    contact_name: Mapped[str | None] = mapped_column(String(80))
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(120))
    address: Mapped[str | None] = mapped_column(String(200))
    payment_terms: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(default=True)


class PurchaseOrder(IdMixin, TimestampMixin, Base):
    __tablename__ = "purchase_orders"
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    status: Mapped[str] = mapped_column(String(12), default="draft")  # draft|sent|partial|received|cancelled
    expected_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    total_cents: Mapped[int] = mapped_column(default=0)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    items: Mapped[list["PurchaseOrderItem"]] = relationship(cascade="all, delete-orphan")


class PurchaseOrderItem(IdMixin, Base):
    __tablename__ = "purchase_order_items"
    order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id", ondelete="CASCADE"))
    stock_item_id: Mapped[int] = mapped_column(ForeignKey("stock_items.id"))
    qty: Mapped[float] = mapped_column(Float)
    unit_cost_cents: Mapped[float] = mapped_column(Float, default=0)
    # What already arrived (partial receipts add up; the order is «received» when nothing is pending).
    received_qty: Mapped[float] = mapped_column(Float, default=0, server_default="0")


class Purchase(IdMixin, TimestampMixin, Base):
    __tablename__ = "purchases"
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    purchase_order_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_orders.id"))
    invoice_number: Mapped[str | None] = mapped_column(String(40))
    invoice_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)
    total_cents: Mapped[int] = mapped_column(default=0)
    paid_cents: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(12), default="pending")  # pending|partial|paid
    notes: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    # Photo of the delivery note (remito) taken at the warehouse; kept outside the public /uploads (`<datos>/receipts/`).
    remito_path: Mapped[str | None] = mapped_column(String(40))
    items: Mapped[list["PurchaseItem"]] = relationship(cascade="all, delete-orphan")
    payments: Mapped[list["SupplierPayment"]] = relationship(cascade="all, delete-orphan")


class PurchaseItem(IdMixin, Base):
    __tablename__ = "purchase_items"
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"))
    stock_item_id: Mapped[int] = mapped_column(ForeignKey("stock_items.id"))
    qty: Mapped[float] = mapped_column(Float)
    unit_cost_cents: Mapped[float] = mapped_column(Float)
    expiry_date: Mapped[date | None] = mapped_column(Date)


class SupplierPayment(IdMixin, Base):
    __tablename__ = "supplier_payments"
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"))
    amount_cents: Mapped[int]
    method: Mapped[str] = mapped_column(String(30))
    cash_session_id: Mapped[int | None] = mapped_column(ForeignKey("cash_sessions.id"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
