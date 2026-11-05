from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import Manager, require_role
from app.db import get_db
from app.models import User
from app.schemas.common import Ok
from app.schemas.stock import (
    AdjustIn,
    CountCreate,
    CountItemPatch,
    CountItemsPatch,
    CountOut,
    MovementOut,
    StockCategoryIn,
    StockCategoryOut,
    StockItemIn,
    StockItemOut,
    StockItemUpdate,
    StockSummary,
    SuggestionGroup,
    WasteIn,
)
from app.services import free_plan
from app.services import stock_ops as svc

router = APIRouter(prefix="/api", tags=["stock"])

Reader = Depends(require_role("encargado", "barista"))


# ---- Categories
@router.get("/stock/categories", response_model=list[StockCategoryOut])
def list_categories(db: Session = Depends(get_db), _: User = Reader):
    return svc.list_categories(db)


@router.post("/stock/categories", response_model=StockCategoryOut)
def create_category(data: StockCategoryIn, db: Session = Depends(get_db), me: User = Manager):
    return svc.create_category(db, data, me)


@router.patch("/stock/categories/{category_id}", response_model=StockCategoryOut)
def update_category(category_id: int, data: StockCategoryIn, db: Session = Depends(get_db), me: User = Manager):
    return svc.update_category(db, category_id, data, me)


@router.delete("/stock/categories/{category_id}", response_model=Ok)
def delete_category(category_id: int, db: Session = Depends(get_db), me: User = Manager) -> Ok:
    svc.delete_category(db, category_id, me)
    return Ok()


# ---- Summary & suggestions
@router.get("/stock/summary", response_model=StockSummary)
def summary(db: Session = Depends(get_db), _: User = Reader) -> StockSummary:
    return svc.summary(db)


@router.get("/stock/suggestions", response_model=list[SuggestionGroup])
def suggestions(supplier_id: int | None = None, db: Session = Depends(get_db), _: User = Reader):
    return svc.suggestions(db, supplier_id)


# ---- Items
@router.get("/stock/items", response_model=list[StockItemOut])
def list_items(
    category_id: int | None = None,
    status: str | None = None,
    include_inactive: bool = False,
    q: str | None = None,
    db: Session = Depends(get_db),
    _: User = Reader,
):
    return svc.list_items(db, category_id=category_id, status=status, include_inactive=include_inactive, q=q)


@router.get("/stock/items/{item_id}", response_model=StockItemOut)
def get_item(item_id: int, db: Session = Depends(get_db), _: User = Reader) -> StockItemOut:
    return svc.get_item(db, item_id)


@router.post("/stock/items", response_model=StockItemOut)
def create_item(data: StockItemIn, db: Session = Depends(get_db), me: User = Manager) -> StockItemOut:
    free_plan.check_can_create(db, "stock_items")
    return svc.create_item(db, data, me)


@router.patch("/stock/items/{item_id}", response_model=StockItemOut)
def update_item(item_id: int, data: StockItemUpdate, db: Session = Depends(get_db), me: User = Manager):
    return svc.update_item(db, item_id, data, me)


@router.delete("/stock/items/{item_id}", response_model=Ok)
def delete_item(item_id: int, db: Session = Depends(get_db), me: User = Manager) -> Ok:
    svc.deactivate_item(db, item_id, me)
    return Ok()


@router.get("/stock/items/{item_id}/movements", response_model=list[MovementOut])
def item_movements(
    item_id: int, limit: int = 200, type: str | None = None, db: Session = Depends(get_db), _: User = Reader
):
    return svc.movements(db, item_id, min(max(limit, 1), 1000), type)


# ---- Adjust / waste
@router.post("/stock/adjust", response_model=StockItemOut)
def adjust(data: AdjustIn, db: Session = Depends(get_db), me: User = Manager) -> StockItemOut:
    return svc.adjust(db, data, me)


@router.post("/stock/waste", response_model=StockItemOut)
def waste(data: WasteIn, db: Session = Depends(get_db), me: User = Manager) -> StockItemOut:
    return svc.waste(db, data, me)


# ---- Physical counts
@router.get("/stock/counts", response_model=list[CountOut])
def list_counts(db: Session = Depends(get_db), _: User = Reader):
    return svc.list_counts(db)


@router.post("/stock/counts", response_model=CountOut)
def create_count(data: CountCreate, db: Session = Depends(get_db), me: User = Manager) -> CountOut:
    return svc.create_count(db, data, me)


@router.get("/stock/counts/{count_id}", response_model=CountOut)
def get_count(count_id: int, db: Session = Depends(get_db), _: User = Reader) -> CountOut:
    return svc.get_count(db, count_id)


@router.patch("/stock/counts/{count_id}/items", response_model=CountOut)
def patch_count_items(count_id: int, data: CountItemsPatch, db: Session = Depends(get_db), _: User = Manager):
    return svc.set_counted_bulk(db, count_id, data.items)


@router.patch("/stock/counts/{count_id}/items/{item_id}", response_model=CountOut)
def patch_count_item(
    count_id: int, item_id: int, data: CountItemPatch, db: Session = Depends(get_db), _: User = Manager
):
    return svc.set_counted(db, count_id, item_id, data.counted_qty)


@router.post("/stock/counts/{count_id}/apply", response_model=CountOut)
def apply_count(count_id: int, db: Session = Depends(get_db), me: User = Manager) -> CountOut:
    return svc.apply_count(db, count_id, me)


@router.post("/stock/counts/{count_id}/cancel", response_model=CountOut)
def cancel_count(count_id: int, db: Session = Depends(get_db), me: User = Manager) -> CountOut:
    return svc.cancel_count(db, count_id, me)
