"""Supplies by channel ("Insumos según el canal") of a product or a category (default)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import CurrentUser, Perm
from app.db import get_db
from app.models import User
from app.services import channel_supplies as svc

router = APIRouter(prefix="/api", tags=["catalog"])
Editor = Perm("catalog.edit")


@router.get("/products/{product_id}/channel-supplies")
def product_supplies(product_id: int, db: Session = Depends(get_db), _: User = CurrentUser) -> dict:
    return svc.get_product(db, product_id)


@router.put("/products/{product_id}/channel-supplies")
def put_product_supplies(product_id: int, data: svc.SuppliesIn, db: Session = Depends(get_db), user: User = Editor) -> dict:
    return svc.put(db, user, data, product_id=product_id)


@router.get("/product-categories/{category_id}/channel-supplies")
def category_supplies(category_id: int, db: Session = Depends(get_db), _: User = CurrentUser) -> dict:
    return svc.get_category(db, category_id)


@router.put("/product-categories/{category_id}/channel-supplies")
def put_category_supplies(category_id: int, data: svc.SuppliesIn, db: Session = Depends(get_db), user: User = Editor) -> dict:
    return svc.put(db, user, data, category_id=category_id)
