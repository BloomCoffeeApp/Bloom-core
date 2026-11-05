"""Order screen (bar/kitchen), open tabs and order metrics."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

OrderStatus = Literal["pending", "received", "preparing", "ready", "delivered", "cancelled"]
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


class OrderOut(BaseModel):
    id: int
    number: int
    source: Literal["pos", "table"]
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


class WaiterCallOut(BaseModel):
    id: int
    table_id: int
    table_label: str
    kind: Literal["waiter", "bill"]
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
