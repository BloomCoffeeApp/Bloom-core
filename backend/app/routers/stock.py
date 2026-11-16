from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from app.auth import Perm
from app.db import get_db
from app.models import User
from app.schemas.common import Ok
from app.schemas.stock import (
    AdjustIn,
    CountCreate,
    CountItemPatch,
    CountItemsPatch,
    CountOut,
    LotOut,
    MovementOut,
    PackagesIn,
    QuickDiscardIn,
    QuickItemOut,
    StockCategoryIn,
    StockCategoryOut,
    StockItemIn,
    StockItemOut,
    StockItemUpdate,
    StockSummary,
    SuggestionGroup,
    WasteIn,
)
from app.services import free_plan, idempotency
from app.services import stock_ops as svc

router = APIRouter(prefix="/api", tags=["stock"])

Reader = Perm("stock.view")
Manager = Perm("stock.edit")
Adjuster = Perm("stock.adjust")
# Loading the quantities of a count: whoever adjusts stock, or the warehouse (applying it stays with the adjusters).
Counter = Perm("stock.adjust", "stock.count")


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
def _once(response: Response, db: Session, raw_key: str | None, scope: str, me: User, payload, run, load):
    """Runs the operation once per `Idempotency-Key` (a double tap or a retry doesn't repeat it)."""
    out, repeated = idempotency.once(db, idempotency.clean_key(raw_key), scope, me, payload, run, load)
    if repeated:
        response.headers["Idempotent-Replay"] = "true"
    return out


@router.post("/stock/adjust", response_model=StockItemOut)
def adjust(data: AdjustIn, response: Response, db: Session = Depends(get_db), me: User = Adjuster,
           idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> StockItemOut:
    return _once(response, db, idempotency_key, "stock_adjust", me, data, lambda k: svc.adjust(db, data, me, k),
                 lambda i: svc.get_item(db, i))


@router.post("/stock/waste", response_model=StockItemOut)
def waste(data: WasteIn, response: Response, db: Session = Depends(get_db), me: User = Adjuster,
          idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> StockItemOut:
    """Descartar: a quantity, N packages or everything left (optionally of one lot), with a reason."""
    return _once(response, db, idempotency_key, "stock_waste", me, data, lambda k: svc.waste(db, data, me, _key=k),
                 lambda i: svc.get_item(db, i))


# Quick discard of small spills from the POS / barista (people who sell or prepare, not only stock managers).
QuickDiscarder = Perm("pos.sell", "barista.use", "kitchen.use", "stock.adjust")


@router.get("/stock/quick-items", response_model=list[QuickItemOut])
def quick_items(db: Session = Depends(get_db), _: User = QuickDiscarder):
    return svc.quick_items(db)


@router.post("/stock/quick-discard", response_model=Ok)
def quick_discard(data: QuickDiscardIn, db: Session = Depends(get_db), me: User = QuickDiscarder) -> Ok:
    svc.quick_discard(db, data, me)
    return Ok()


@router.get("/stock/items/{item_id}/lots", response_model=list[LotOut])
def item_lots(item_id: int, db: Session = Depends(get_db), _: User = Reader):
    return svc.lots(db, item_id)


@router.put("/stock/items/{item_id}/packages", response_model=StockItemOut)
def set_packages(item_id: int, data: PackagesIn, db: Session = Depends(get_db), me: User = Manager) -> StockItemOut:
    return svc.set_packages(db, item_id, data.packages, me)


# ---- Physical counts
@router.get("/stock/counts", response_model=list[CountOut])
def list_counts(db: Session = Depends(get_db), _: User = Reader):
    return svc.list_counts(db)


@router.post("/stock/counts", response_model=CountOut)
def create_count(data: CountCreate, response: Response, db: Session = Depends(get_db), me: User = Counter,
                 idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> CountOut:
    return _once(response, db, idempotency_key, "stock_count_create", me, data, lambda k: svc.create_count(db, data, me, k),
                 lambda i: svc.get_count(db, i))


@router.get("/stock/counts/{count_id}", response_model=CountOut)
def get_count(count_id: int, db: Session = Depends(get_db), _: User = Reader) -> CountOut:
    return svc.get_count(db, count_id)


@router.patch("/stock/counts/{count_id}/items", response_model=CountOut)
def patch_count_items(count_id: int, data: CountItemsPatch, db: Session = Depends(get_db), _: User = Counter):
    return svc.set_counted_bulk(db, count_id, data.items)


@router.patch("/stock/counts/{count_id}/items/{item_id}", response_model=CountOut)
def patch_count_item(
    count_id: int, item_id: int, data: CountItemPatch, db: Session = Depends(get_db), _: User = Counter
):
    return svc.set_counted(db, count_id, item_id, data.counted_qty)


@router.post("/stock/counts/{count_id}/apply", response_model=CountOut)
def apply_count(count_id: int, response: Response, db: Session = Depends(get_db), me: User = Adjuster,
                idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> CountOut:
    return _once(response, db, idempotency_key, "stock_count_apply", me, {"count_id": count_id},
                 lambda k: svc.apply_count(db, count_id, me, k), lambda i: svc.get_count(db, i))


@router.post("/stock/counts/{count_id}/cancel", response_model=CountOut)
def cancel_count(count_id: int, db: Session = Depends(get_db), me: User = Adjuster) -> CountOut:
    return svc.cancel_count(db, count_id, me)
