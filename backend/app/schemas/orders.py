"""Order screen (bar/kitchen), open tabs and order metrics."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

OrderStatus = Literal[
    "pending", "received", "accepted", "awaiting_pay", "paid", "preparing", "ready", "dispatched", "delivered",
    "cancelled", "rejected", "expired",
]
Level = Literal["pending", "ok", "warn", "late"]


class ChannelFlags(BaseModel):
    salon: bool = True
    llevar: bool = True
    delivery: bool = True


class ChannelTargets(BaseModel):
    salon: int = Field(default=8, ge=1, le=240)
    llevar: int = Field(default=5, ge=1, le=240)
    delivery: int = Field(default=15, ge=1, le=240)


class OrdersSettings(BaseModel):
    enabled: bool = True
    channels: ChannelFlags = ChannelFlags()
    targets: ChannelTargets = ChannelTargets()
    warn_pct: int = Field(default=75, ge=10, le=100)  # yellow from this % of the target


class OrderItemOut(BaseModel):
    id: int
    product_id: int | None
    name: str
    size_name: str | None
    qty: float
    modifiers: list[str]
    notes: str | None


class OrderAction(BaseModel):
    """A button of the order's current state (services/order_flows.py)."""

    to: str
    label: str
    tone: str
    place: str
    needs: str | None = None
    icon: str | None = None


class CustomerChange(BaseModel):
    field: str
    label: str
    saved: str | None = None
    new: str | None = None


class OnlineInfo(BaseModel):
    customer_id: int | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    address: str | None = None
    address_ref: str | None = None
    delivery_zone: str | None = None
    delivery_fee_cents: int = 0
    total_cents: int = 0
    payment_method: str | None = None
    payment_url: str | None = None
    charge_id: int | None = None  # collection charge (services/collect.py) of an online payment
    refunded_cents: int = 0
    eta_minutes: int | None = None
    accepted_at: datetime | None = None
    paid_at: datetime | None = None
    expires_at: datetime | None = None
    expires_in_s: int | None = None
    tracking_url: str | None = None
    cancel_reason: str | None = None
    sale_registered: bool = False
    invoice_request: dict[str, str | None] | None = None  # «Pedir factura» from the tracking page
    customer_changes: list[CustomerChange] = []


class OrderOut(BaseModel):
    id: int
    number: int
    source: Literal["pos", "table", "online"]
    status: OrderStatus
    channel: str
    table_id: int | None
    table_label: str | None
    station_id: int | None = None
    sale_id: int | None
    sale_number: int | None
    note: str | None
    target_minutes: int
    created_at: datetime
    received_at: datetime | None
    started_at: datetime | None
    ready_at: datetime | None
    prepared_by_name: str | None
    items: list[OrderItemOut]
    elapsed_s: int
    late: bool
    level: Level
    flow: str = "caja"  # caja | mesa | take_away | delivery
    status_label: str = ""
    column: str = "queue"  # confirm | payment | queue | preparing | ready | done
    actions: list[OrderAction] = []
    payment_status: str = "unpaid"
    online: OnlineInfo | None = None


class WaiterCallOut(BaseModel):
    id: int
    table_id: int
    table_label: str
    kind: Literal["waiter", "bill", "invoice"]
    created_at: datetime
    elapsed_s: int


class StationRef(BaseModel):
    id: int
    name: str
    print_tickets: bool
    direct_print: bool = False  # its kitchen tickets go straight to a thermal printer (backend)


class PrintFailure(BaseModel):
    order_id: int
    error: str


class BoardOut(BaseModel):
    server_time: datetime
    settings: OrdersSettings
    pro: bool = False  # `orders_pro`: stations, per-product targets, pickup screen
    stations: list[StationRef] = []
    orders: list[OrderOut]
    calls: list[WaiterCallOut]
    late_count: int
    print_failures: list[PrintFailure] = []


class OrderStatusIn(BaseModel):
    status: OrderStatus
    reason: str | None = Field(default=None, max_length=200)
    eta_minutes: int | None = Field(default=None, ge=1, le=600)  # «Aceptar» an online order


class TabLineOut(BaseModel):
    product_id: int | None
    name: str
    size_id: int | None
    size_name: str | None
    qty: float
    modifier_ids: list[int]
    modifiers: list[str]
    notes: str | None
    unit_price_cents: int


class TabOut(BaseModel):
    id: int
    table_id: int
    table_label: str
    opened_at: datetime
    orders: int
    unfinished: int
    lines: list[TabLineOut]
    total_cents: int
    prepaid_cents: int = 0  # already paid from the phones (Mercado Pago): the cashier collects total − this
    paying_cents: int = 0  # a payment from a phone is in progress: charging the table waits for it


class OrdersSummary(BaseModel):
    orders: int
    avg_prep_s: int | None
    late: int
    late_pct: float | None
    open: int
    open_late: int


class MetricRow(BaseModel):
    key: str
    label: str
    orders: int
    avg_prep_s: int | None
    late: int
    late_pct: float | None
    qty: float | None = None


class MetricTotals(BaseModel):
    orders: int
    avg_prep_s: int | None
    late: int
    late_pct: float | None


class OrderMetricsOut(BaseModel):
    from_: str = Field(alias="from")
    to: str
    totals: MetricTotals
    by_hour: list[MetricRow]
    by_channel: list[MetricRow]
    by_product: list[MetricRow]
    by_user: list[MetricRow]

    model_config = {"populate_by_name": True}
