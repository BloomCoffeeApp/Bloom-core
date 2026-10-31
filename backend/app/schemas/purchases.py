from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORM


# ---------- Suppliers ----------
class SupplierIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    cuit: str | None = None
    contact_name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    payment_terms: str | None = None
    notes: str | None = None
    active: bool = True


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    cuit: str | None = None
    contact_name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    payment_terms: str | None = None
    notes: str | None = None
    active: bool | None = None


class SupplierOut(ORM):
    id: int
    name: str
    cuit: str | None
    contact_name: str | None
    phone: str | None
    email: str | None
    address: str | None
    payment_terms: str | None
    notes: str | None
    active: bool
    debt_cents: int = 0
    item_count: int = 0


# ---------- Lines ----------
class LineIn(BaseModel):
    stock_item_id: int
    qty: float = Field(gt=0)
    unit_cost_cents: float = Field(ge=0)
    expiry_date: date | None = None


class LineOut(BaseModel):
    id: int
    stock_item_id: int
    stock_item_name: str
    unit: str
    qty: float
    unit_cost_cents: float
    subtotal_cents: int
    expiry_date: date | None = None


# ---------- Purchase orders ----------
class OrderIn(BaseModel):
    supplier_id: int
    expected_date: date | None = None
    notes: str | None = None
    items: list[LineIn] = Field(min_length=1)


class OrderUpdate(BaseModel):
    expected_date: date | None = None
    notes: str | None = None
    items: list[LineIn] | None = None


class OrderOut(BaseModel):
    id: int
    supplier_id: int
    supplier_name: str
    status: str
    expected_date: date | None
    notes: str | None
    total_cents: int
    created_by: int | None
    created_at: datetime
    items: list[LineOut]
    purchase_id: int | None = None


class FromSuggestionsIn(BaseModel):
    supplier_id: int


class ReceiveIn(BaseModel):
    invoice_number: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    notes: str | None = None
    items: list[LineIn] | None = None


class OrderText(BaseModel):
    text: str


# ---------- Purchases (invoices) ----------
class PurchaseIn(BaseModel):
    supplier_id: int
    invoice_number: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    notes: str | None = None
    items: list[LineIn] = Field(min_length=1)


class PaymentIn(BaseModel):
    amount_cents: int = Field(gt=0)
    method: str = Field(min_length=1, max_length=30)


class PaymentOut(ORM):
    id: int
    purchase_id: int
    amount_cents: int
    method: str
    cash_session_id: int | None
    user_id: int | None
    ts: datetime


class PurchaseOut(BaseModel):
    id: int
    supplier_id: int
    supplier_name: str
    purchase_order_id: int | None
    invoice_number: str | None
    invoice_date: date
    due_date: date | None
    total_cents: int
    paid_cents: int
    balance_cents: int
    status: str
    overdue: bool
    notes: str | None
    created_at: datetime
    items: list[LineOut] = []
    payments: list[PaymentOut] = []


class SupplierAccount(BaseModel):
    supplier: SupplierOut
    debt_cents: int
    overdue_cents: int
    total_purchased_cents: int
    pending: list[PurchaseOut]
    upcoming: list[PurchaseOut]
    recent_payments: list[PaymentOut]
