from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORM

# ---------- Payment methods ----------


class PaymentMethodOut(ORM):
    id: int
    code: str
    name: str
    surcharge_pct: float
    sort_order: int
    active: bool


class PaymentMethodUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    active: bool | None = None


# ---------- Cash ----------


class CashOpenIn(BaseModel):
    opening_cents: int = Field(ge=0)


class CashMovementIn(BaseModel):
    type: Literal["in", "out"]
    amount_cents: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=200)


class CashMovementOut(ORM):
    id: int
    type: str
    amount_cents: int
    reason: str
    user_id: int | None
    user_name: str | None = None
    ts: datetime


class CashCountIn(BaseModel):
    payment_method: str
    counted_cents: int = Field(ge=0)


class CashCloseIn(BaseModel):
    counts: list[CashCountIn] = []
    notes: str | None = None


class MethodTotal(BaseModel):
    method: str
    name: str
    sales_cents: int
    count: int
    expected_cents: int
    counted_cents: int | None = None
    difference_cents: int | None = None


class CategoryTotal(BaseModel):
    category_id: int | None
    name: str
    qty: float
    total_cents: int


class CashSessionOut(BaseModel):
    id: int
    status: str
    opened_at: datetime
    opened_by: int
    opened_by_name: str | None
    closed_at: datetime | None
    closed_by: int | None
    closed_by_name: str | None
    opening_cents: int
    notes: str | None
    sales_total_cents: int
    tickets: int
    avg_ticket_cents: int
    voided_count: int
    voided_total_cents: int
    courtesy_count: int = 0
    courtesy_cents: int = 0
    courtesy_cost_cents: int = 0
    discounts_cents: int
    movements_in_cents: int
    movements_out_cents: int
    expected_cash_cents: int
    difference_cents: int | None
    by_method: list[MethodTotal]
    movements: list[CashMovementOut]


class CashSessionDetail(CashSessionOut):
    by_category: list[CategoryTotal]
    business: dict[str, Any]


class CashSessionListItem(BaseModel):
    id: int
    status: str
    opened_at: datetime
    closed_at: datetime | None
    opened_by_name: str | None
    closed_by_name: str | None
    opening_cents: int
    sales_total_cents: int
    tickets: int
    difference_cents: int | None


# ---------- Sales ----------


class SaleItemIn(BaseModel):
    product_id: int
    qty: float = Field(default=1, gt=0, le=1000)
    size_id: int | None = None  # required choice for sized products (defaults to the product's default size)
    modifier_ids: list[int] = []
    notes: str | None = Field(default=None, max_length=200)
    discount_cents: int = Field(default=0, ge=0)
    # False for lines that already reached the bar (e.g. charged from a table's tab).
    to_bar: bool = True
    # Pro `loyalty_pro`: this line is the free product of a stamp card ($0, stock moves).
    reward_program_id: int | None = None


class PaymentIn(BaseModel):
    method: str
    amount_cents: int = Field(ge=0)
    tendered_cents: int | None = Field(default=None, ge=0)


class SaleIn(BaseModel):
    items: list[SaleItemIn] = Field(min_length=1)
    customer_id: int | None = None
    channel: Literal["salon", "llevar", "delivery"] = "salon"
    table_label: str | None = Field(default=None, max_length=20)
    discount_cents: int = Field(default=0, ge=0)
    discount_pct: float | None = Field(default=None, ge=0, le=100)
    # Delivery charge (only `delivery` channel): adds to the total; discounts and points ignore it.
    delivery_fee_cents: int = Field(default=0, ge=0, le=10**9)
    tip_cents: int = Field(default=0, ge=0, le=10**9)  # optional tip on top of the total (needs Configuración → Propinas)
    points_to_redeem: int = Field(default=0, ge=0)
    payments: list[PaymentIn] = []
    notes: str | None = None
    # Courtesy ("invita la casa"): stock moves, nothing is charged (no payments, discounts or points).
    is_courtesy: bool = False
    courtesy_reason: str | None = Field(default=None, max_length=200)
    # Charging a table's open tab ("mesa abierta"): the tab closes with this sale.
    tab_id: int | None = None
    # Pro `loyalty_pro`: redeem a stamp card whose reward is a discount on this sale.
    reward_program_id: int | None = None


class QuoteIn(BaseModel):
    items: list[SaleItemIn] = Field(min_length=1, max_length=200)


class QuoteLineOut(BaseModel):
    index: int
    promo_id: int | None
    promo_name: str | None
    discount_cents: int


class QuoteOut(BaseModel):
    lines: list[QuoteLineOut]


class SaleVoidIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


class SaleItemOut(ORM):
    id: int
    product_id: int | None
    name_snapshot: str
    size_id: int | None = None
    size_name: str | None = None
    qty: float
    unit_price_cents: int
    discount_cents: int
    total_cents: int
    cost_cents: int
    modifiers: list[dict[str, Any]] | None
    notes: str | None
    promo_id: int | None = None
    promo_name: str | None = None
    promo_discount_cents: int = 0
    reward_program_id: int | None = None
    courtesy_reason: str | None = None


class SalePaymentOut(ORM):
    id: int
    method: str
    amount_cents: int
    tendered_cents: int | None
    change_cents: int


class CustomerMini(BaseModel):
    id: int
    name: str
    phone: str | None
    points: int
    balance_cents: int


class SaleOut(BaseModel):
    id: int
    number: int
    ts: datetime
    status: str
    is_courtesy: bool = False
    courtesy_cents: int = 0
    courtesy_reason: str | None = None
    channel: str
    table_label: str | None
    cash_session_id: int | None
    user_id: int | None
    user_name: str | None
    customer_id: int | None
    customer_name: str | None
    subtotal_cents: int
    discount_cents: int
    delivery_fee_cents: int = 0
    tip_cents: int = 0
    points_discount_cents: int
    total_cents: int
    cost_cents: int
    points_earned: int
    points_redeemed: int
    reward_discount_cents: int = 0
    notes: str | None
    void_reason: str | None
    voided_by: int | None
    voided_by_name: str | None
    voided_at: datetime | None
    methods: list[str]
    items_count: float


class SaleTableTab(BaseModel):
    id: int
    table_label: str | None


class SaleDetail(SaleOut):
    items: list[SaleItemOut]
    payments: list[SalePaymentOut]
    customer: CustomerMini | None
    change_cents: int
    # Set while the sale is completed and charged a table's tab (voiding it reopens that tab).
    table_tab: SaleTableTab | None = None


class SaleListOut(BaseModel):
    items: list[SaleOut]
    total: int
    page: int
    page_size: int
    sum_total_cents: int


class TicketOut(BaseModel):
    business: dict[str, Any]
    sale: SaleDetail
    payment_names: dict[str, str]
