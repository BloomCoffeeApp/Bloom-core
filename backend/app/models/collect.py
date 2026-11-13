"""Collecting payments for the cafe (QR, Point, payment links, transfers) and customer-facing screens.

See services/collect.py. Money goes to the cafe's own account (e.g. its Mercado Pago), never to Bloom.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, utcnow

CHARGE_STATUSES = ("pending", "approved", "rejected", "cancelled", "expired", "refunded")
OPEN_STATUSES = ("pending",)


class CollectCharge(IdMixin, Base):
    """One attempt to collect money: a dynamic QR, a Point order, a payment link or a manual transfer."""

    __tablename__ = "collect_charges"
    __table_args__ = (Index("ix_collect_charges_status_next_poll", "status", "next_poll_at"),)
    provider: Mapped[str] = mapped_column(String(30))  # mercadopago | fake | manual
    kind: Mapped[str] = mapped_column(String(10))  # qr | link | point | transfer
    # Our reference, sent to the provider as external_reference ([A-Za-z0-9_-], no personal data).
    ref: Mapped[str] = mapped_column(String(64), unique=True)
    # Who asked for it: "pos_sale" (POS checkout) or another module ("online_order" …) and its id.
    ref_type: Mapped[str] = mapped_column(String(30), default="pos_sale")
    ref_id: Mapped[int | None]
    provider_id: Mapped[str | None] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(12), default="pending")
    status_detail: Mapped[str | None] = mapped_column(String(60))
    # The provider's payment / operation number (shown on the customer's receipt).
    operation_id: Mapped[str | None] = mapped_column(String(40))
    amount_cents: Mapped[int]
    refunded_cents: Mapped[int] = mapped_column(default=0, server_default="0")
    description: Mapped[str] = mapped_column(String(150))
    qr_data: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(500))
    device_id: Mapped[str | None] = mapped_column(String(80))
    # Cart summary for the customer screen: [{"name", "qty", "total_cents"}].
    items: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    # POS checkout: the SaleIn payload that becomes a sale when the payment is approved.
    sale_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    sale_id: Mapped[int | None] = mapped_column(ForeignKey("sales.id"), index=True)
    screen_id: Mapped[int | None] = mapped_column(ForeignKey("customer_screens.id", ondelete="SET NULL"))
    # Approved but the follow-up (create the sale, mark the order paid…) failed: shown to the cashier.
    error: Mapped[str | None] = mapped_column(String(300))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    # Polling (no webhooks reach the cafe PC): when to ask the provider next, and consecutive failures.
    next_poll_at: Mapped[datetime | None] = mapped_column(DateTime)
    poll_failures: Mapped[int] = mapped_column(default=0, server_default="0")


class CollectRefund(IdMixin, Base):
    __tablename__ = "collect_refunds"
    charge_id: Mapped[int] = mapped_column(ForeignKey("collect_charges.id", ondelete="CASCADE"), index=True)
    amount_cents: Mapped[int]
    provider_refund_id: Mapped[str | None] = mapped_column(String(80))
    reason: Mapped[str | None] = mapped_column(String(200))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CustomerScreen(IdMixin, Base):
    """A tablet/TV on the local network that shows the customer what to pay (/pantalla-cliente?token=…)."""

    __tablename__ = "customer_screens"
    name: Mapped[str] = mapped_column(String(60))
    # Secret in the screen's URL (rotatable). Plain text: the admin can show the link/QR again, and it
    # only grants reading what that screen displays.
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    active: Mapped[bool] = mapped_column(default=True)
    current_charge_id: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)
