from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import Perm
from app.db import get_db
from app.models import Customer, CustomerAccountMovement, LoyaltyTransaction, User
from app.schemas.common import Ok
from app.schemas.customers import (
    AccountMovementOut,
    CustomerCreate,
    CustomerDetail,
    CustomerListItem,
    CustomerOut,
    CustomerSalesPage,
    CustomerStats,
    CustomerUpdate,
    LoyaltyTxOut,
    PaymentIn,
    PointsIn,
)
from app.services import customers as svc
from app.services import free_plan

router = APIRouter(prefix="/api", tags=["customers"])

Staff = Perm("customers.edit")
Manager = Perm("customers.manage")


@router.get("/customers", response_model=list[CustomerListItem])
def list_customers(
    q: str | None = None,
    segment: str | None = None,
    order: str | None = None,
    include_inactive: bool = False,
    limit: int | None = Query(default=None, ge=1, le=2000),
    db: Session = Depends(get_db),
    _: User = Staff,
) -> list[dict[str, Any]]:
    return svc.list_customers(db, q, segment, order, include_inactive, limit)


@router.get("/customers/stats", response_model=CustomerStats)
def customer_stats(db: Session = Depends(get_db), _: User = Staff) -> dict[str, Any]:
    return svc.stats(db)


@router.post("/customers", response_model=CustomerOut)
def create_customer(data: CustomerCreate, db: Session = Depends(get_db), user: User = Staff) -> Customer:
    free_plan.check_can_create(db, "customers")
    return svc.create(db, data.model_dump(), user)


@router.get("/customers/{customer_id}", response_model=CustomerDetail)
def get_customer(customer_id: int, db: Session = Depends(get_db), _: User = Staff) -> dict[str, Any]:
    return svc.detail(db, svc.get_or_404(db, customer_id))


@router.patch("/customers/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: int, data: CustomerUpdate, db: Session = Depends(get_db), user: User = Staff
) -> Customer:
    c = svc.get_or_404(db, customer_id)
    return svc.update(db, c, data.model_dump(exclude_unset=True), user)


@router.delete("/customers/{customer_id}", response_model=Ok)
def delete_customer(customer_id: int, db: Session = Depends(get_db), user: User = Manager) -> Ok:
    svc.deactivate(db, svc.get_or_404(db, customer_id), user)
    return Ok()


@router.get("/customers/{customer_id}/sales", response_model=CustomerSalesPage)
def customer_sales(
    customer_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Staff,
) -> dict[str, Any]:
    svc.get_or_404(db, customer_id)
    return svc.sales_page(db, customer_id, page, page_size)


@router.post("/customers/{customer_id}/payments", response_model=AccountMovementOut)
def register_payment(
    customer_id: int, data: PaymentIn, db: Session = Depends(get_db), user: User = Staff
) -> CustomerAccountMovement:
    c = svc.get_or_404(db, customer_id)
    return svc.register_payment(db, c, data.amount_cents, data.method, user)


@router.post("/customers/{customer_id}/points", response_model=LoyaltyTxOut)
def adjust_points(
    customer_id: int, data: PointsIn, db: Session = Depends(get_db), user: User = Manager
) -> LoyaltyTransaction:
    c = svc.get_or_404(db, customer_id)
    return svc.adjust_points(db, c, data.points, data.reason, user)
