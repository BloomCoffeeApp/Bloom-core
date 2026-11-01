"""Response schemas for dashboard, reports and system endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Kpis(BaseModel):
    sales_cents: int
    tickets: int
    avg_ticket_cents: int
    gross_margin_cents: int | None
    margin_pct: float | None


class KpiDeltas(BaseModel):
    sales_cents: float | None
    tickets: float | None
    avg_ticket_cents: float | None
    gross_margin_cents: float | None


class HourPoint(BaseModel):
    hour: int
    label: str
    sales_cents: int
    avg_cents: int


class DayPoint(BaseModel):
    date: str
    label: str
    tickets: int
    sales_cents: int


class SizeBreakdown(BaseModel):
    size_id: int | None
    name: str
    qty: float
    sales_cents: int


class TopProduct(BaseModel):
    product_id: int | None
    name: str
    qty: float
    sales_cents: int
    sizes: list[SizeBreakdown] = []  # only for products sold by size


class MixRow(BaseModel):
    key: str
    label: str
    sales_cents: int
    pct: float


class RecentSale(BaseModel):
    id: int
    number: int
    ts: datetime
    total_cents: int
    status: str
    is_courtesy: bool = False
    courtesy_cents: int = 0
    channel: str
    user_name: str | None
    items_count: float
    payment_methods: list[str]


class DashboardOut(BaseModel):
    from_: str = Field(alias="from")
    to: str
    days: int
    show_costs: bool
    compare_from: str
    compare_to: str
    compare_label: str
    kpis: Kpis
    previous: Kpis
    deltas: KpiDeltas
    hourly: list[HourPoint]
    hourly_mode: str
    daily: list[DayPoint]
    top_products: list[TopProduct]
    payment_mix: list[MixRow]
    category_mix: list[MixRow]
    channel_mix: list[MixRow]
    recent_sales: list[RecentSale]


class SalesRow(BaseModel):
    key: str
    label: str
    tickets: int
    qty: float | None
    sales_cents: int
    cost_cents: int
    margin_cents: int
    margin_pct: float | None


class SalesReport(BaseModel):
    group_by: str
    rows: list[SalesRow]
    totals: SalesRow


class ProductRow(SalesRow):
    product_id: int
    category: str
    active: bool
    price_cents: int
    unit_cost_cents: int
    unit_margin_cents: int
    unit_margin_pct: float | None
    rank: int
    sizes: list[dict[str, Any]] = []  # per-size rows (sold in the period and/or current sizes)


class ProductsReport(BaseModel):
    rows: list[ProductRow]
    totals: dict[str, Any]


class MovementRow(BaseModel):
    id: int
    ts: datetime
    stock_item_id: int
    stock_item: str
    unit: str
    type: str
    type_label: str
    qty: float
    unit_cost_cents: float
    value_cents: int
    balance_after: float
    reason: str | None
    ref: str | None
    user_name: str | None


class MovementSummary(BaseModel):
    type: str
    label: str
    count: int
    value_cents: int


class MovementsReport(BaseModel):
    rows: list[MovementRow]
    summary: list[MovementSummary]
    totals: dict[str, Any]


class WasteRow(BaseModel):
    stock_item_id: int
    stock_item: str
    unit: str
    events: int
    qty: float
    value_cents: int
    pct: float


class WasteReport(BaseModel):
    rows: list[WasteRow]
    totals: dict[str, Any]


class PurchaseRow(BaseModel):
    key: str
    label: str
    purchases: int
    total_cents: int
    paid_cents: int
    pending_cents: int


class PurchasesReport(BaseModel):
    group_by: str
    rows: list[PurchaseRow]
    totals: dict[str, Any]


class CashSessionRow(BaseModel):
    id: int
    opened_at: datetime
    closed_at: datetime | None
    opened_by: str | None
    closed_by: str | None
    status: str
    status_label: str
    opening_cents: int
    tickets: int
    sales_cents: int
    cash_sales_cents: int
    movements_in_cents: int
    movements_out_cents: int
    expected_cents: int | None
    counted_cents: int | None
    difference_cents: int | None


class CashSessionsReport(BaseModel):
    rows: list[CashSessionRow]
    totals: dict[str, Any]


# ---------------------------------------------------------------- system

class BackupOut(BaseModel):
    name: str
    size_bytes: int
    created_at: datetime
    label: str


class SystemInfo(BaseModel):
    app_name: str
    version: str
    data_dir: str
    db_path: str
    db_size_bytes: int
    backups_count: int
    last_backup: BackupOut | None
    lan_ips: list[str]
    lan_url: str | None
    port: int
    lan_enabled: bool
    lan_active: bool
    network_public: bool


class RestoreIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class RestoreOut(BaseModel):
    ok: bool = True
    restored: str
    safety_backup: str
    restart_required: bool = True
    message: str


class AuditRow(BaseModel):
    id: int
    ts: datetime
    user_id: int | None
    user_name: str | None
    action: str
    entity: str
    entity_id: int | None
    payload: dict[str, Any] | None
