from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import CurrentUser, Manager
from app.db import get_db
from app.models import User
from app.schemas.catalog import (
    BulkPriceIn,
    BulkPriceOut,
    CategoryIn,
    CategoryOut,
    CategoryUpdate,
    ModifierGroupIn,
    ModifierGroupOut,
    ModifierGroupUpdate,
    PosCatalogOut,
    PriceHistoryOut,
    ProductIn,
    ProductOut,
    ProductUpdate,
)
from app.schemas.common import Ok
from app.services import catalog as svc

router = APIRouter(prefix="/api", tags=["catalog"])


# ---- POS
@router.get("/pos/catalog", response_model=PosCatalogOut)
def pos_catalog(db: Session = Depends(get_db), _: User = CurrentUser) -> PosCatalogOut:
    return svc.pos_catalog(db)


# ---- Categories
@router.get("/product-categories", response_model=list[CategoryOut])
def list_categories(include_inactive: bool = True, db: Session = Depends(get_db), _: User = CurrentUser):
    return svc.list_categories(db, include_inactive)


@router.post("/product-categories", response_model=CategoryOut)
def create_category(data: CategoryIn, db: Session = Depends(get_db), me: User = Manager):
    return CategoryOut.model_validate(svc.create_category(db, data, me))


@router.patch("/product-categories/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, data: CategoryUpdate, db: Session = Depends(get_db), me: User = Manager):
    return CategoryOut.model_validate(svc.update_category(db, category_id, data, me))


@router.delete("/product-categories/{category_id}", response_model=Ok)
def delete_category(category_id: int, db: Session = Depends(get_db), me: User = Manager) -> Ok:
    svc.update_category(db, category_id, CategoryUpdate(active=False), me)
    return Ok()


# ---- Products
@router.get("/products", response_model=list[ProductOut])
def list_products(
    category_id: int | None = None,
    include_inactive: bool = False,
    q: str | None = None,
    db: Session = Depends(get_db),
    _: User = CurrentUser,
):
    return svc.list_products(db, category_id=category_id, include_inactive=include_inactive, q=q)


@router.post("/products/bulk-price", response_model=BulkPriceOut)
def bulk_price(data: BulkPriceIn, db: Session = Depends(get_db), me: User = Manager) -> BulkPriceOut:
    return svc.bulk_price(db, data, me)


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db), _: User = CurrentUser) -> ProductOut:
    return svc.get_product(db, product_id)


@router.post("/products", response_model=ProductOut)
def create_product(data: ProductIn, db: Session = Depends(get_db), me: User = Manager) -> ProductOut:
    return svc.create_product(db, data, me)


@router.patch("/products/{product_id}", response_model=ProductOut)
def update_product(product_id: int, data: ProductUpdate, db: Session = Depends(get_db), me: User = Manager) -> ProductOut:
    return svc.update_product(db, product_id, data, me)


@router.delete("/products/{product_id}", response_model=Ok)
def delete_product(product_id: int, db: Session = Depends(get_db), me: User = Manager) -> Ok:
    svc.deactivate_product(db, product_id, me)
    return Ok()


@router.get("/products/{product_id}/price-history", response_model=list[PriceHistoryOut])
def price_history(product_id: int, db: Session = Depends(get_db), _: User = Manager):
    return svc.price_history(db, product_id)


# ---- Modifier groups
@router.get("/modifier-groups", response_model=list[ModifierGroupOut])
def list_groups(db: Session = Depends(get_db), _: User = CurrentUser):
    return svc.list_groups(db)


@router.post("/modifier-groups", response_model=ModifierGroupOut)
def create_group(data: ModifierGroupIn, db: Session = Depends(get_db), me: User = Manager) -> ModifierGroupOut:
    return svc.create_group(db, data, me)


@router.patch("/modifier-groups/{group_id}", response_model=ModifierGroupOut)
def update_group(group_id: int, data: ModifierGroupUpdate, db: Session = Depends(get_db), me: User = Manager):
    return svc.update_group(db, group_id, data, me)


@router.delete("/modifier-groups/{group_id}", response_model=Ok)
def delete_group(group_id: int, db: Session = Depends(get_db), me: User = Manager) -> Ok:
    svc.delete_group(db, group_id, me)
    return Ok()
