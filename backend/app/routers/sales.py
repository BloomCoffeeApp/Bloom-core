from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import AdminOnly, CurrentUser, require_role
from app.db import get_db
from app.models import CashSession, PaymentMethod, User
from app.schemas.sales import (
    CashCloseIn,
    CashMovementIn,
    CashMovementOut,
    CashOpenIn,
    CashSessionDetail,
    CashSessionListItem,
    CashSessionOut,
    PaymentMethodOut,
    PaymentMethodUpdate,
    SaleDetail,
    SaleIn,
    SaleListOut,
    SaleVoidIn,
    TicketOut,
)
from app.services import cash as cash_svc
from app.services import sales as sales_svc

router = APIRouter(prefix="/api", tags=["sales"])

Seller = Depends(require_role("cajero", "encargado"))
Manager = Depends(require_role("encargado"))


@router.get("/payment-methods", response_model=list[PaymentMethodOut])
def payment_methods(
    include_inactive: bool = False, db: Session = Depends(get_db), user: User = CurrentUser
) -> list[PaymentMethod]:
    # Disabled methods are only relevant to whoever can re-enable them.
    return sales_svc.list_payment_methods(db, include_inactive and user.role == "admin")


@router.patch("/payment-methods/{method_id}", response_model=PaymentMethodOut)
def update_payment_method(
    method_id: int, data: PaymentMethodUpdate, db: Session = Depends(get_db), user: User = AdminOnly
) -> PaymentMethod:
    return sales_svc.update_payment_method(db, method_id, data, user)


@router.get("/pos/config")
def pos_config(db: Session = Depends(get_db), user: User = CurrentUser) -> dict:
    """Settings the POS needs to preview totals (the backend always recalculates)."""
    return {"loyalty": sales_svc.loyalty_cfg(db), "can_discount": sales_svc.can_discount(user)}


# ---------- Cash ----------


@router.get("/cash/current", response_model=CashSessionOut | None)
def cash_current(db: Session = Depends(get_db), _: User = CurrentUser) -> dict | None:
    s = cash_svc.get_open_session(db)
    return cash_svc.session_summary(db, s) if s else None


@router.post("/cash/open", response_model=CashSessionOut)
def cash_open(data: CashOpenIn, db: Session = Depends(get_db), user: User = Seller) -> dict:
    s = cash_svc.open_session(db, data.opening_cents, user)
    return cash_svc.session_summary(db, s)


@router.post("/cash/movements", response_model=CashMovementOut)
def cash_movement(data: CashMovementIn, db: Session = Depends(get_db), user: User = Seller) -> dict:
    mv = cash_svc.add_movement(db, data.type, data.amount_cents, data.reason, user)
    return {**CashMovementOut.model_validate(mv).model_dump(), "user_name": user.name}


@router.post("/cash/close", response_model=CashSessionDetail)
def cash_close(data: CashCloseIn, db: Session = Depends(get_db), user: User = Seller) -> dict:
    s = cash_svc.close_session(db, [(c.payment_method, c.counted_cents) for c in data.counts], data.notes, user)
    return cash_svc.session_summary(db, s, detail=True)


@router.get("/cash/sessions", response_model=list[CashSessionListItem])
def cash_sessions(
    limit: int = Query(60, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: User = Seller,
) -> list[dict]:
    return cash_svc.list_sessions(db, limit, offset)


@router.get("/cash/sessions/{session_id}", response_model=CashSessionDetail)
def cash_session_detail(session_id: int, db: Session = Depends(get_db), _: User = Seller) -> dict:
    s = db.get(CashSession, session_id)
    if s is None:
        raise HTTPException(404, "Sesión de caja no encontrada")
    return cash_svc.session_summary(db, s, detail=True)


# ---------- Sales ----------


@router.post("/sales", response_model=SaleDetail)
def create_sale(data: SaleIn, db: Session = Depends(get_db), user: User = Seller) -> dict:
    sale = sales_svc.create_sale(db, data, user)
    return sales_svc.get_detail(db, sale.id)


@router.get("/sales", response_model=SaleListOut)
def list_sales(
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = None,
    user_id: int | None = None,
    customer_id: int | None = None,
    method: str | None = None,
    number: int | None = None,
    cash_session_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Seller,
) -> dict:
    return sales_svc.list_sales(
        db,
        date_from=date_from,
        date_to=date_to,
        status=status,
        user_id=user_id,
        customer_id=customer_id,
        method=method,
        number=number,
        cash_session_id=cash_session_id,
        page=page,
        page_size=page_size,
    )


@router.get("/sales/{sale_id}", response_model=SaleDetail)
def sale_detail(sale_id: int, db: Session = Depends(get_db), _: User = Seller) -> dict:
    return sales_svc.get_detail(db, sale_id)


@router.post("/sales/{sale_id}/void", response_model=SaleDetail)
def void_sale(sale_id: int, data: SaleVoidIn, db: Session = Depends(get_db), user: User = Manager) -> dict:
    sales_svc.void_sale(db, sale_id, data.reason, user)
    return sales_svc.get_detail(db, sale_id)


@router.get("/sales/{sale_id}/ticket", response_model=TicketOut)
def sale_ticket(sale_id: int, db: Session = Depends(get_db), _: User = Seller) -> dict:
    return sales_svc.ticket(db, sale_id)
