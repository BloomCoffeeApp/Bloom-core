import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORM

Kind = Literal["fixed", "variable"]
Status = Literal["paid", "pending"]
Period = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")


class ExpenseCategoryOut(ORM):
    id: int
    name: str
    kind: Kind
    active: bool
    sort_order: int


class ExpenseCategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    kind: Kind = "variable"


class ExpenseCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    kind: Kind | None = None
    active: bool | None = None
    sort_order: int | None = None


class ExpenseIn(BaseModel):
    category_id: int
    kind: Kind | None = None  # default: the category's
    description: str = Field(min_length=1, max_length=200)
    amount_cents: int = Field(gt=0, le=100_000_000_000)
    date: dt.date | None = None  # default: today (local)
    status: Status = "paid"
    due_date: dt.date | None = None
    payment_method: str | None = Field(default=None, max_length=30)
    # Paid in cash with money from the open drawer: creates the cash "egreso" in the same transaction.
    from_cash: bool = False
    notes: str | None = Field(default=None, max_length=1000)


class ExpenseUpdate(BaseModel):
    category_id: int | None = None
    kind: Kind | None = None
    description: str | None = Field(default=None, min_length=1, max_length=200)
    amount_cents: int | None = Field(default=None, gt=0, le=100_000_000_000)
    date: dt.date | None = None
    due_date: dt.date | None = None
    payment_method: str | None = Field(default=None, max_length=30)
    notes: str | None = Field(default=None, max_length=1000)


class ExpensePayIn(BaseModel):
    payment_method: str | None = Field(default=None, max_length=30)
    amount_cents: int | None = Field(default=None, gt=0, le=100_000_000_000)  # the real amount (e.g. this month's bill)
    from_cash: bool = False


class ExpenseOut(BaseModel):
    id: int
    category_id: int
    category_name: str
    kind: Kind
    description: str
    amount_cents: int
    date: dt.date
    due_date: dt.date | None
    status: Status
    overdue: bool
    paid_at: dt.datetime | None
    payment_method: str | None
    payment_method_name: str | None
    from_cash: bool
    recurring_id: int | None
    period: str | None
    has_receipt: bool
    notes: str | None
    created_at: dt.datetime


class CategoryTotal(BaseModel):
    category_id: int
    name: str
    count: int
    total_cents: int
    pct: float


class ExpenseTotals(BaseModel):
    total_cents: int
    paid_cents: int
    pending_cents: int
    overdue_cents: int
    fixed_cents: int
    variable_cents: int
    count: int


class ExpenseList(BaseModel):
    period: str
    items: list[ExpenseOut]
    totals: ExpenseTotals
    by_category: list[CategoryTotal]


class RecurringIn(BaseModel):
    category_id: int
    description: str = Field(min_length=1, max_length=200)
    amount_cents: int = Field(gt=0, le=100_000_000_000)
    day_of_month: int = Field(default=10, ge=1, le=31)
    payment_method: str | None = Field(default=None, max_length=30)
    start_period: str | None = Period
    notes: str | None = Field(default=None, max_length=1000)


class RecurringUpdate(BaseModel):
    category_id: int | None = None
    description: str | None = Field(default=None, min_length=1, max_length=200)
    amount_cents: int | None = Field(default=None, gt=0, le=100_000_000_000)
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    payment_method: str | None = Field(default=None, max_length=30)
    active: bool | None = None
    notes: str | None = Field(default=None, max_length=1000)


class RecurringOut(BaseModel):
    id: int
    category_id: int
    category_name: str
    description: str
    amount_cents: int
    day_of_month: int
    payment_method: str | None
    payment_method_name: str | None
    active: bool
    start_period: str
    last_period: str | None
    notes: str | None


class ResultOut(BaseModel):
    """Ventas − costo de mercadería − cortesías/mermas − gastos = ganancia real."""

    model_config = {"populate_by_name": True}
    from_: str = Field(alias="from")
    to: str
    sales_cents: int
    tickets: int
    cogs_cents: int
    gross_margin_cents: int
    waste_cents: int
    courtesy_cost_cents: int
    losses_cents: int
    expenses_cents: int
    expenses_pending_cents: int
    profit_cents: int
    profit_pct: float | None


class PreviousResultOut(ResultOut):
    period: str
    expenses_upcoming_cents: int = 0


class MonthResultOut(BaseModel):
    period: str
    partial: bool  # current month: sales up to today, the month's expenses in full
    current: PreviousResultOut  # + expenses_upcoming_cents: this month's expenses dated after today
    previous: PreviousResultOut
