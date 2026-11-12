"""Employees, time clock and advances (Pro feature "staff"; code in bloom_pro).

Internal control only: hours and an estimated pay, never a legal payslip.
Personal data kept minimal: name, position, an optional phone and notes.
"""

import datetime as dt

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, utcnow


class Employee(IdMixin, TimestampMixin, Base):
    __tablename__ = "employees"
    name: Mapped[str] = mapped_column(String(80))
    # App user (clocks in with that user's PIN). Without one, the employee has an own clock PIN.
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), unique=True)
    clock_pin_hash: Mapped[str | None] = mapped_column(String(255))
    position: Mapped[str | None] = mapped_column(String(60))
    pay_type: Mapped[str] = mapped_column(String(10), default="hourly")  # hourly | monthly
    hourly_rate_cents: Mapped[int] = mapped_column(default=0)
    monthly_salary_cents: Mapped[int] = mapped_column(default=0)
    start_date: Mapped[dt.date | None] = mapped_column(Date)
    phone: Mapped[str | None] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str] = mapped_column(String(20), default="amber")
    active: Mapped[bool] = mapped_column(default=True)


class TimeEntry(IdMixin, TimestampMixin, Base):
    """One shift: clock-in to clock-out (open while `clock_out` is NULL), minus breaks."""

    __tablename__ = "time_entries"
    __table_args__ = (Index("ix_time_entries_employee_in", "employee_id", "clock_in"),)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    clock_in: Mapped[dt.datetime] = mapped_column(DateTime)
    clock_out: Mapped[dt.datetime | None] = mapped_column(DateTime)
    break_minutes: Mapped[int] = mapped_column(default=0)
    break_started_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    source: Mapped[str] = mapped_column(String(10), default="clock")  # clock | manual
    note: Mapped[str | None] = mapped_column(String(200))
    edited_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class StaffAdvance(IdMixin, Base):
    """Advance on pay ("adelanto"): deducted from the estimate of the period that contains `date`."""

    __tablename__ = "staff_advances"
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    amount_cents: Mapped[int]
    date: Mapped[dt.date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(String(200))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
