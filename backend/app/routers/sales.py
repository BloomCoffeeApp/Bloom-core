from datetime import date, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, Perm
from app.db import get_db
from app.licensing import current_status, free_limits
from app.models import CashSession, PaymentMethod, Sale, User
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
    QuoteIn,
    QuoteOut,
    SaleDetail,
    SaleIn,
    SaleListOut,
    SaleVoidIn,
    TicketOut,
)
from app.services import cash as cash_svc
from app.services import idempotency
from app.services import roles
from app.services import sales as sales_svc
from app.services import settings as settings_svc
from app.services.timeutil import local_today

router = APIRouter(prefix="/api", tags=["sales"])

Seller = Perm("pos.sell")
Cashier = Perm("cash.open_close")
CashMoves = Perm("cash.movements")
Voider = Perm("sales.void")
SettingsAdmin = Perm("settings.manage")


@router.get("/payment-methods", response_model=list[PaymentMethodOut])
def payment_methods(
    include_inactive: bool = False, db: Session = Depends(get_db), user: User = CurrentUser
) -> list[PaymentMethod]:
    # Disabled methods are only relevant to whoever can re-enable them.
    return sales_svc.list_payment_methods(db, include_inactive and roles.has(user, "settings.manage"))


@router.patch("/payment-methods/{method_id}", response_model=PaymentMethodOut)
def update_payment_method(
    method_id: int, data: PaymentMethodUpdate, db: Session = Depends(get_db), user: User = SettingsAdmin
) -> PaymentMethod:
    return sales_svc.update_payment_method(db, method_id, data, user)


@router.get("/pos/config")
def pos_config(db: Session = Depends(get_db), user: User = CurrentUser) -> dict:
    """Settings the POS needs to preview totals (the backend always recalculates)."""
    return {"loyalty": sales_svc.loyalty_cfg(db), "can_discount": sales_svc.can_discount(user), "tips": settings_svc.get(db, "tips")}


@router.post("/pos/quote", response_model=QuoteOut)
def pos_quote(data: QuoteIn, db: Session = Depends(get_db), _: User = Seller) -> dict:
    """Automatic promotions of a cart (Pro `promos`; none in the free edition)."""
    return {"lines": sales_svc.quote(db, data.items)}


# ---------- Cash ----------


@router.get("/cash/current", response_model=CashSessionOut | None)
def cash_current(db: Session = Depends(get_db), _: User = CurrentUser) -> dict | None:
    s = cash_svc.get_open_session(db)
    return cash_svc.session_summary(db, s) if s else None


@router.post("/cash/open", response_model=CashSessionOut)
def cash_open(data: CashOpenIn, db: Session = Depends(get_db), user: User = Cashier) -> dict:
    s = cash_svc.open_session(db, data.opening_cents, user)
    return cash_svc.session_summary(db, s)


@router.post("/cash/movements", response_model=CashMovementOut)
def cash_movement(
    data: CashMovementIn,
    response: Response,
    db: Session = Depends(get_db),
    user: User = CashMoves,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    mv, repeated = cash_svc.add_movement(db, data.type, data.amount_cents, data.reason, user, idempotency.clean_key(idempotency_key))
    if repeated:
        response.headers["Idempotent-Replay"] = "true"
    return {**CashMovementOut.model_validate(mv).model_dump(), "user_name": user.name}


@router.post("/cash/close", response_model=CashSessionDetail)
def cash_close(data: CashCloseIn, db: Session = Depends(get_db), user: User = Cashier) -> dict:
    s = cash_svc.close_session(db, [(c.payment_method, c.counted_cents) for c in data.counts], data.notes, user)
    return cash_svc.session_summary(db, s, detail=True)


@router.get("/cash/sessions", response_model=list[CashSessionListItem])
def cash_sessions(
    limit: int = Query(60, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: User = Cashier,
) -> list[dict]:
    return cash_svc.list_sessions(db, limit, offset)


@router.get("/cash/sessions/{session_id}", response_model=CashSessionDetail)
def cash_session_detail(session_id: int, db: Session = Depends(get_db), _: User = Cashier) -> dict:
    s = db.get(CashSession, session_id)
    if s is None:
        raise HTTPException(404, "Sesión de caja no encontrada")
    return cash_svc.session_summary(db, s, detail=True)


# ---------- Sales ----------


@router.post("/sales", response_model=SaleDetail)
def create_sale(
    data: SaleIn,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Seller,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    """With an `Idempotency-Key` header the same sale sent twice is registered once and the repeat returns it
    (header `Idempotent-Replay: true`). Without the header it behaves as it always did."""
    sale, repeated = sales_svc.create_sale_once(db, data, user, idempotency.clean_key(idempotency_key))
    if repeated:
        response.headers["Idempotent-Replay"] = "true"
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
    if not current_status().valid:  # free plan: only the recent history is browsable
        earliest = local_today() - timedelta(days=free_limits()["sales_history_days"])
        date_from = max(date_from or earliest, earliest)
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
def void_sale(sale_id: int, data: SaleVoidIn, db: Session = Depends(get_db), user: User = Voider) -> dict:
    sale = db.get(Sale, sale_id)
    settled = bool(sale and sale.tip_payout_id and sale.tip_cents)  # its tip was already shared (Pro `staff`)
    sales_svc.void_sale(db, sale_id, data.reason, user)
    out = sales_svc.get_detail(db, sale_id)
    if settled:
        out["warnings"] = ["La propina de esta venta ya estaba liquidada: la liquidación no se modifica "
                           "(si hace falta, ajustala por afuera)."]
    return out


@router.get("/sales/{sale_id}/ticket", response_model=TicketOut)
def sale_ticket(sale_id: int, db: Session = Depends(get_db), _: User = Seller) -> dict:
    return sales_svc.ticket(db, sale_id)
