"""Business expenses ("Gestión de gastos"): categories, recurring templates and the expenses themselves.

Money in integer cents. `Expense.date` is the LOCAL calendar date the expense belongs to (accrual:
rent of November counts in November whether it was paid or not); `paid_at` is the UTC moment it was
paid. Merchandise purchases are NOT expenses here: they reach the result through the cost of what was
sold (sales.cost_cents).
"""

import datetime as dt

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin

EXPENSE_KINDS = ("fixed", "variable")
EXPENSE_STATUSES = ("paid", "pending")


class ExpenseCategory(IdMixin, TimestampMixin, Base):
    __tablename__ = "expense_categories"
    name: Mapped[str] = mapped_column(String(60), unique=True)
    # Suggested kind for new expenses of this category (the expense keeps its own).
    kind: Mapped[str] = mapped_column(String(10), default="variable")
    active: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(default=0)


class RecurringExpense(IdMixin, TimestampMixin, Base):
    """Monthly fixed expense: every month a pending expense is generated with its due date."""

    __tablename__ = "recurring_expenses"
    category_id: Mapped[int] = mapped_column(ForeignKey("expense_categories.id"))
    description: Mapped[str] = mapped_column(String(200))
    amount_cents: Mapped[int]
    day_of_month: Mapped[int] = mapped_column(default=10)  # due day (clamped to the month's length)
    payment_method: Mapped[str | None] = mapped_column(String(30))
    active: Mapped[bool] = mapped_column(default=True)
    start_period: Mapped[str] = mapped_column(String(7))  # "YYYY-MM": first month generated
    last_period: Mapped[str | None] = mapped_column(String(7))  # last month generated (never regenerated)
    notes: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class Expense(IdMixin, TimestampMixin, Base):
    __tablename__ = "expenses"
    __table_args__ = (
        UniqueConstraint("recurring_id", "period", name="uq_expenses_recurring_period"),
        Index("ix_expenses_date", "date"),
        Index("ix_expenses_status_due", "status", "due_date"),
    )
    category_id: Mapped[int] = mapped_column(ForeignKey("expense_categories.id"))
    kind: Mapped[str] = mapped_column(String(10), default="variable")  # fixed | variable
    description: Mapped[str] = mapped_column(String(200))
    amount_cents: Mapped[int]
    date: Mapped[dt.date] = mapped_column(Date)
    due_date: Mapped[dt.date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), default="paid")  # paid | pending
    paid_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    payment_method: Mapped[str | None] = mapped_column(String(30))
    # Paid in cash from the open drawer: the "egreso" created in the same transaction.
    cash_movement_id: Mapped[int | None] = mapped_column(ForeignKey("cash_movements.id", ondelete="SET NULL"))
    recurring_id: Mapped[int | None] = mapped_column(ForeignKey("recurring_expenses.id", ondelete="SET NULL"))
    period: Mapped[str | None] = mapped_column(String(7))  # "YYYY-MM" for generated recurring expenses
    receipt_path: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
