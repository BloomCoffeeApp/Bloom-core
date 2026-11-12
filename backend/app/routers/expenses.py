"""Gestión de gastos (core, Free): categories, expenses, monthly fixed expenses, receipt photo and the
month's "ganancia real". The full month-by-month result report is Pro (`/api/reports/profit`)."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth import Perm
from app.db import get_db
from app.models import User
from app.schemas.common import Ok
from app.schemas.expenses import (
    ExpenseCategoryIn,
    ExpenseCategoryOut,
    ExpenseCategoryUpdate,
    ExpenseIn,
    ExpenseList,
    ExpenseOut,
    ExpensePayIn,
    ExpenseUpdate,
    MonthResultOut,
    RecurringIn,
    RecurringOut,
    RecurringUpdate,
)
from app.services import expenses as svc
from app.services.product_images import MAX_UPLOAD_BYTES

router = APIRouter(prefix="/api/expenses", tags=["expenses"])
Manager = Perm("expenses.manage")
MonthQ = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")


# ---- categories
@router.get("/categories", response_model=list[ExpenseCategoryOut])
def list_categories(db: Session = Depends(get_db), _: User = Manager):
    return svc.list_categories(db)


@router.post("/categories", response_model=ExpenseCategoryOut)
def create_category(data: ExpenseCategoryIn, db: Session = Depends(get_db), user: User = Manager):
    return svc.create_category(db, data.name, data.kind, user)


@router.patch("/categories/{category_id}", response_model=ExpenseCategoryOut)
def update_category(category_id: int, data: ExpenseCategoryUpdate, db: Session = Depends(get_db), user: User = Manager):
    return svc.update_category(db, category_id, data.model_dump(exclude_unset=True), user)


# ---- monthly fixed expenses
@router.get("/recurring", response_model=list[RecurringOut])
def list_recurring(db: Session = Depends(get_db), _: User = Manager):
    return svc.list_recurring(db)


@router.post("/recurring", response_model=Ok)
def create_recurring(data: RecurringIn, db: Session = Depends(get_db), user: User = Manager) -> Ok:
    svc.create_recurring(db, data.model_dump(), user)
    return Ok()


@router.patch("/recurring/{recurring_id}", response_model=Ok)
def update_recurring(recurring_id: int, data: RecurringUpdate, db: Session = Depends(get_db), user: User = Manager) -> Ok:
    svc.update_recurring(db, recurring_id, data.model_dump(exclude_unset=True), user)
    return Ok()


# ---- month result (dashboard card "Ganancia real del mes")
@router.get("/summary", response_model=MonthResultOut)
def month_summary(month: str | None = MonthQ, db: Session = Depends(get_db), _: User = Manager) -> dict:
    return svc.month_result(db, svc.parse_period(month))


# ---- expenses
@router.get("", response_model=ExpenseList)
def list_expenses(
    month: str | None = MonthQ,
    status: str | None = Query(default=None, pattern=r"^(paid|pending)$"),
    category_id: int | None = None,
    kind: str | None = Query(default=None, pattern=r"^(fixed|variable)$"),
    db: Session = Depends(get_db),
    _: User = Manager,
) -> dict:
    return svc.list_expenses(db, svc.parse_period(month), status=status, category_id=category_id, kind=kind)


@router.post("", response_model=ExpenseOut)
def create_expense(data: ExpenseIn, db: Session = Depends(get_db), user: User = Manager) -> dict:
    e = svc.create_expense(db, data.model_dump(), user)
    return svc.get_expense(db, e.id)


@router.patch("/{expense_id}", response_model=ExpenseOut)
def update_expense(expense_id: int, data: ExpenseUpdate, db: Session = Depends(get_db), user: User = Manager) -> dict:
    svc.update_expense(db, expense_id, data.model_dump(exclude_unset=True), user)
    return svc.get_expense(db, expense_id)


@router.post("/{expense_id}/pay", response_model=ExpenseOut)
def pay_expense(expense_id: int, data: ExpensePayIn, db: Session = Depends(get_db), user: User = Manager) -> dict:
    svc.pay_expense(db, expense_id, data.model_dump(), user)
    return svc.get_expense(db, expense_id)


@router.delete("/{expense_id}", response_model=Ok)
def delete_expense(expense_id: int, db: Session = Depends(get_db), user: User = Manager) -> Ok:
    svc.delete_expense(db, expense_id, user)
    return Ok()


# ---- receipt photo (raw body, like product photos; stored outside the public /uploads)
@router.put("/{expense_id}/receipt", response_model=ExpenseOut)
async def upload_receipt(expense_id: int, request: Request, db: Session = Depends(get_db), user: User = Manager) -> dict:
    """Raw image body (Content-Type image/jpeg|png|webp), capped while reading."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "La foto pesa demasiado (máximo 8 MB)")
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "La foto pesa demasiado (máximo 8 MB)")
    ctype = request.headers.get("content-type")

    def go() -> dict:
        svc.save_receipt(db, expense_id, bytes(body), ctype, user)
        return svc.get_expense(db, expense_id)

    return await run_in_threadpool(go)


@router.delete("/{expense_id}/receipt", response_model=ExpenseOut)
def delete_receipt(expense_id: int, db: Session = Depends(get_db), user: User = Manager) -> dict:
    svc.delete_receipt(db, expense_id, user)
    return svc.get_expense(db, expense_id)


@router.get("/{expense_id}/receipt")
def get_receipt(expense_id: int, db: Session = Depends(get_db), _: User = Manager) -> FileResponse:
    return FileResponse(svc.receipt_path_for(db, expense_id), media_type="image/webp", headers={"Cache-Control": "no-store"})
