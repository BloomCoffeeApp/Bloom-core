from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORM


class CustomerBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=120)
    birthday: date | None = None
    notes: str | None = None


class CustomerCreate(CustomerBase):
    credit_limit_cents: int = Field(default=0, ge=0)


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=120)
    birthday: date | None = None
    notes: str | None = None
    credit_limit_cents: int | None = Field(default=None, ge=0)
    active: bool | None = None


class CustomerOut(ORM):
    """Shape used by the POS (search + quick create)."""

    id: int
    name: str
    phone: str | None
    email: str | None
    birthday: date | None
    notes: str | None
    points: int
    balance_cents: int
    credit_limit_cents: int
    active: bool
    created_at: datetime
    # Free plan: visible (and its balance collectable) but not usable in sales (services/free_plan.py).
    locked: bool = False


class CustomerListItem(CustomerOut):
    last_visit_at: datetime | None = None
    visits: int = 0
    visits_30d: int = 0
    total_spent_cents: int = 0


class FavoriteProduct(BaseModel):
    product_id: int | None
    name: str
    qty: float


class CustomerMetrics(BaseModel):
    total_spent_cents: int
    tickets: int
    avg_ticket_cents: int
    first_visit_at: datetime | None
    last_visit_at: datetime | None
    days_since_last_visit: int | None
    visits_per_month: float
    visits_30d: int
    favorite_product: FavoriteProduct | None
    top_products: list[FavoriteProduct]


class AccountMovementOut(ORM):
    id: int
    amount_cents: int
    type: str
    method: str | None
    sale_id: int | None
    user_id: int | None
    ts: datetime


class LoyaltyTxOut(ORM):
    id: int
    points: int
    reason: str
    sale_id: int | None
    ts: datetime


class CustomerDetail(CustomerOut):
    metrics: CustomerMetrics
    account_movements: list[AccountMovementOut]
    loyalty_transactions: list[LoyaltyTxOut]
    over_limit: bool


class CustomerSaleOut(BaseModel):
    id: int
    number: int
    ts: datetime
    total_cents: int
    status: str
    channel: str
    items_count: float
    items_summary: str
    payment_methods: list[str]


class CustomerSalesPage(BaseModel):
    items: list[CustomerSaleOut]
    total: int
    page: int
    page_size: int


class PaymentIn(BaseModel):
    amount_cents: int = Field(gt=0)
    method: str = Field(default="efectivo", min_length=1, max_length=30)


class PointsIn(BaseModel):
    points: int
    reason: str = Field(min_length=1, max_length=120)


class BirthdayCustomer(BaseModel):
    id: int
    name: str
    phone: str | None


class CustomerStats(BaseModel):
    total: int
    activos_30d: int
    nuevos_mes: int
    deuda_total_cents: int
    deudores: int
    cumpleanos_hoy: list[BirthdayCustomer]
