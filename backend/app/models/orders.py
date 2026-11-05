"""Order queue (bar/kitchen screen), dining tables, open tabs per table and waiter calls.

Core owns the schema (the order screen is core). Customers ordering from their table (QR + token)
are a Pro capability (`public_menu`) built on the same tables.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin, utcnow

# pending = sent by a customer, waiting for a waiter/cashier to confirm it (never reaches the bar before)
ORDER_STATUSES = ("pending", "received", "preparing", "ready", "delivered", "cancelled")
ORDER_SOURCES = ("pos", "table")


class OrderStation(IdMixin, TimestampMixin, Base):
    """Pro (`orders_pro`): a preparation station with its own screen (\"Barra\", \"Cocina\"). Items are
    routed by category (`ProductCategory.station_id`); one sale becomes one order per station."""

    __tablename__ = "order_stations"
    name: Mapped[str] = mapped_column(String(40))
    sort_order: Mapped[int] = mapped_column(default=0)
    active: Mapped[bool] = mapped_column(default=True)
    # The station's screen prints a kitchen ticket for every new order.
    print_tickets: Mapped[bool] = mapped_column(default=False)


class DiningTable(IdMixin, TimestampMixin, Base):
    __tablename__ = "dining_tables"
    label: Mapped[str] = mapped_column(String(20))
    sort_order: Mapped[int] = mapped_column(default=0)
    active: Mapped[bool] = mapped_column(default=True)
    # Secret printed in the table's QR (rotatable): without it nobody can order for this table.
    token: Mapped[str] = mapped_column(String(32), unique=True)


class TableTab(IdMixin, Base):
    """\"Mesa abierta\": confirmed orders of a table accumulate here until the cashier charges them
    (one sale). `payment_ref` is reserved for paying the tab by Mercado Pago QR (later)."""

    __tablename__ = "table_tabs"
    table_id: Mapped[int] = mapped_column(ForeignKey("dining_tables.id"), index=True)
    # open|closed|merged (merged = its sale was voided and its orders moved to the table's open tab)
    status: Mapped[str] = mapped_column(String(10), default="open")
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    sale_id: Mapped[int | None] = mapped_column(ForeignKey("sales.id"))
    payment_ref: Mapped[str | None] = mapped_column(String(80))


class Order(IdMixin, Base):
    __tablename__ = "orders"
    number: Mapped[int]  # per local day (#1, #2…), what the bar calls out
    source: Mapped[str] = mapped_column(String(10), default="pos")  # pos|table
    status: Mapped[str] = mapped_column(String(12), default="received", index=True)
    channel: Mapped[str] = mapped_column(String(10), default="salon")
    table_id: Mapped[int | None] = mapped_column(ForeignKey("dining_tables.id"))
    table_label: Mapped[str | None] = mapped_column(String(20))
    tab_id: Mapped[int | None] = mapped_column(ForeignKey("table_tabs.id"), index=True)
    station_id: Mapped[int | None] = mapped_column(ForeignKey("order_stations.id"), index=True)
    sale_id: Mapped[int | None] = mapped_column(ForeignKey("sales.id"), index=True)
    note: Mapped[str | None] = mapped_column(String(200))
    target_minutes: Mapped[int] = mapped_column(default=10)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    # Enters the bar queue (POS: on sale; table: on confirmation). Timers and metrics start here.
    received_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancel_reason: Mapped[str | None] = mapped_column(String(200))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    prepared_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))  # who took/finished it
    # Customer orders: the phone's address (rate limits) and the secret it polls its status with.
    client_ip: Mapped[str | None] = mapped_column(String(64))
    public_key: Mapped[str | None] = mapped_column(String(32))
    # Reserved for online payment of a customer order (Mercado Pago, later): unpaid|paid.
    payment_status: Mapped[str] = mapped_column(String(10), default="unpaid", server_default="unpaid")
    payment_ref: Mapped[str | None] = mapped_column(String(80))
    items: Mapped[list["OrderItem"]] = relationship(cascade="all, delete-orphan", order_by="OrderItem.id")


class OrderItem(IdMixin, Base):
    __tablename__ = "order_items"
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), index=True)
    name_snapshot: Mapped[str] = mapped_column(String(160))
    size_id: Mapped[int | None]
    size_name: Mapped[str | None] = mapped_column(String(60))
    qty: Mapped[float] = mapped_column(Float, default=1)
    unit_price_cents: Mapped[int] = mapped_column(default=0)
    modifiers: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(String(200))
    prep_minutes: Mapped[int | None]  # snapshot of the product's prep time (None = channel default)


class WaiterCall(IdMixin, Base):
    __tablename__ = "waiter_calls"
    table_id: Mapped[int] = mapped_column(ForeignKey("dining_tables.id"), index=True)
    kind: Mapped[str] = mapped_column(String(10), default="waiter")  # waiter|bill
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    client_ip: Mapped[str | None] = mapped_column(String(64))
