"""Stock operations: items, kardex, adjustments, waste, physical counts and purchase suggestions.

Every quantity change goes through app.services.stock.apply_movement.
"""

import math
from collections import defaultdict
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    InventoryCount,
    InventoryCountItem,
    StockCategory,
    StockItem,
    StockLot,
    StockMovement,
    Supplier,
    User,
    utcnow,
)
from app.schemas.stock import (
    AdjustIn,
    CountCreate,
    CountItemOut,
    CountItemRow,
    CountOut,
    MovementOut,
    StockCategoryIn,
    StockCategoryOut,
    StockItemIn,
    StockItemOut,
    StockItemUpdate,
    StockSummary,
    SuggestionGroup,
    SuggestionItem,
    WasteIn,
)
from app.services import audit, free_plan
from app.services.stock import apply_movement

CONSUMPTION_TYPES = ("sale", "internal", "waste")
SUGGESTION_DAYS = 14


# ---------------------------------------------------------------- helpers
def item_status(item: StockItem) -> str:
    if item.current_qty <= 0:
        return "out"
    if item.min_qty > 0 and item.current_qty <= item.min_qty:
        return "low"
    return "ok"


def item_value_cents(item: StockItem) -> int:
    return round(max(item.current_qty, 0) * item.avg_cost_cents)


def _get_item(db: Session, item_id: int) -> StockItem:
    item = db.get(StockItem, item_id)
    if not item:
        raise HTTPException(404, "Insumo no encontrado")
    return item


def _lookups(db: Session) -> tuple[dict[int, str], dict[int, str]]:
    cats = dict(db.execute(select(StockCategory.id, StockCategory.name)).all())
    sups = dict(db.execute(select(Supplier.id, Supplier.name)).all())
    return cats, sups


def _next_expiry(db: Session) -> dict[int, str]:
    rows = db.execute(
        select(StockLot.stock_item_id, func.min(StockLot.expiry_date))
        .where(StockLot.qty_remaining > 0, StockLot.expiry_date.is_not(None))
        .group_by(StockLot.stock_item_id)
    ).all()
    return {sid: d.isoformat() for sid, d in rows if d}


def item_out(
    item: StockItem, cats: dict[int, str], sups: dict[int, str], expiries: dict[int, str] | None = None,
    usable: frozenset[int] | None = None,
) -> StockItemOut:
    return StockItemOut(
        id=item.id,
        name=item.name,
        category_id=item.category_id,
        category_name=cats.get(item.category_id) if item.category_id else None,
        unit=item.unit,
        current_qty=item.current_qty,
        min_qty=item.min_qty,
        avg_cost_cents=item.avg_cost_cents,
        default_supplier_id=item.default_supplier_id,
        supplier_name=sups.get(item.default_supplier_id) if item.default_supplier_id else None,
        track_expiry=item.track_expiry,
        active=item.active,
        status=item_status(item),
        value_cents=item_value_cents(item),
        next_expiry=(expiries or {}).get(item.id),
        locked=bool(item.active and usable is not None and item.id not in usable),
    )


# ---------------------------------------------------------------- categories
def list_categories(db: Session) -> list[StockCategoryOut]:
    counts = dict(
        db.execute(
            select(StockItem.category_id, func.count(StockItem.id))
            .where(StockItem.active.is_(True))
            .group_by(StockItem.category_id)
        ).all()
    )
    out = []
    for c in db.scalars(select(StockCategory).order_by(StockCategory.name)):
        o = StockCategoryOut.model_validate(c)
        o.item_count = counts.get(c.id, 0)
        out.append(o)
    return out


def create_category(db: Session, data: StockCategoryIn, user: User) -> StockCategoryOut:
    c = StockCategory(name=data.name)
    db.add(c)
    db.flush()
    audit.log(db, user.id, "create", "stock_category", c.id, {"name": c.name})
    db.commit()
    return StockCategoryOut.model_validate(c)


def update_category(db: Session, category_id: int, data: StockCategoryIn, user: User) -> StockCategoryOut:
    c = db.get(StockCategory, category_id)
    if not c:
        raise HTTPException(404, "Categoría no encontrada")
    c.name = data.name
    audit.log(db, user.id, "update", "stock_category", c.id, {"name": c.name})
    db.commit()
    return StockCategoryOut.model_validate(c)


def delete_category(db: Session, category_id: int, user: User) -> None:
    c = db.get(StockCategory, category_id)
    if not c:
        raise HTTPException(404, "Categoría no encontrada")
    in_use = db.scalar(select(func.count(StockItem.id)).where(StockItem.category_id == c.id, StockItem.active.is_(True)))
    if in_use:
        raise HTTPException(409, "La categoría tiene insumos activos")
    for item in db.scalars(select(StockItem).where(StockItem.category_id == c.id)):
        item.category_id = None
    audit.log(db, user.id, "delete", "stock_category", c.id, {"name": c.name})
    db.delete(c)
    db.commit()


# ---------------------------------------------------------------- items
def list_items(
    db: Session,
    *,
    category_id: int | None = None,
    status: str | None = None,
    include_inactive: bool = False,
    q: str | None = None,
) -> list[StockItemOut]:
    query = select(StockItem).order_by(StockItem.name)
    if not include_inactive:
        query = query.where(StockItem.active.is_(True))
    if category_id is not None:
        query = query.where(StockItem.category_id == category_id)
    if q:
        query = query.where(StockItem.name.ilike(f"%{q}%"))
    cats, sups = _lookups(db)
    exp = _next_expiry(db)
    usable = free_plan.active_ids(db, "stock_items")
    out = [item_out(i, cats, sups, exp, usable) for i in db.scalars(query)]
    if status:
        out = [o for o in out if o.status == status]
    return out


def get_item(db: Session, item_id: int) -> StockItemOut:
    cats, sups = _lookups(db)
    return item_out(_get_item(db, item_id), cats, sups, _next_expiry(db), free_plan.active_ids(db, "stock_items"))


def _usable_item(db: Session, item_id: int) -> StockItem:
    """The stock item, or 402 when the free plan locks it (movements need an active one)."""
    item = _get_item(db, item_id)
    free_plan.ensure_usable(db, "stock_items", item.id, item.name)
    return item


def _check_refs(db: Session, category_id: int | None, supplier_id: int | None) -> None:
    if category_id is not None and not db.get(StockCategory, category_id):
        raise HTTPException(400, "Categoría de insumo inexistente")
    if supplier_id is not None and not db.get(Supplier, supplier_id):
        raise HTTPException(400, "Proveedor inexistente")


def create_item(db: Session, data: StockItemIn, user: User) -> StockItemOut:
    _check_refs(db, data.category_id, data.default_supplier_id)
    fields = data.model_dump(exclude={"initial_qty"})
    item = StockItem(**fields, current_qty=0)
    db.add(item)
    db.flush()
    free_plan.on_created(db, "stock_items", item.id)
    if data.initial_qty:
        apply_movement(
            db, item.id, data.initial_qty, "adjustment",
            unit_cost_cents=data.avg_cost_cents, reason="Stock inicial", user_id=user.id,
        )
    audit.log(db, user.id, "create", "stock_item", item.id, data.model_dump())
    db.commit()
    return get_item(db, item.id)


def update_item(db: Session, item_id: int, data: StockItemUpdate, user: User) -> StockItemOut:
    item = _get_item(db, item_id)
    changes = data.model_dump(exclude_unset=True)
    if item.active and set(changes) - {"active"}:
        free_plan.ensure_usable(db, "stock_items", item.id, item.name)  # locked: only archiving
    if changes.get("active") is False and item.active:
        free_plan.on_archived(db, "stock_items", item.id)
    elif changes.get("active") is True and not item.active:
        free_plan.on_reactivated(db, "stock_items", item.id)
    _check_refs(db, changes.get("category_id"), changes.get("default_supplier_id"))
    for k, v in changes.items():
        setattr(item, k, v)
    audit.log(db, user.id, "update", "stock_item", item.id, changes)
    db.commit()
    return get_item(db, item.id)


def deactivate_item(db: Session, item_id: int, user: User) -> None:
    item = _get_item(db, item_id)
    if item.active:
        free_plan.on_archived(db, "stock_items", item.id)
    item.active = False
    audit.log(db, user.id, "deactivate", "stock_item", item.id, {"name": item.name})
    db.commit()


def movements(db: Session, item_id: int, limit: int = 200, type: str | None = None) -> list[MovementOut]:
    _get_item(db, item_id)
    q = (
        select(StockMovement, User.name)
        .outerjoin(User, User.id == StockMovement.user_id)
        .where(StockMovement.stock_item_id == item_id)
        .order_by(StockMovement.ts.desc(), StockMovement.id.desc())
    )
    if type:
        q = q.where(StockMovement.type == type)
    q = q.limit(limit)
    return [
        MovementOut(
            id=m.id, stock_item_id=m.stock_item_id, type=m.type, qty=m.qty, unit_cost_cents=m.unit_cost_cents,
            balance_after=m.balance_after, ref_type=m.ref_type, ref_id=m.ref_id, reason=m.reason,
            user_id=m.user_id, user_name=name, ts=m.ts,
        )
        for m, name in db.execute(q).all()
    ]


# ---------------------------------------------------------------- adjust / waste
def adjust(db: Session, data: AdjustIn, user: User) -> StockItemOut:
    item = _usable_item(db, data.stock_item_id)
    delta = data.delta if data.delta is not None else (data.new_qty or 0) - item.current_qty
    delta = round(delta, 4)
    if abs(delta) < 1e-9:
        raise HTTPException(400, "La cantidad no cambia")
    before = item.current_qty
    mv = apply_movement(db, item.id, delta, "adjustment", reason=data.reason, user_id=user.id)
    db.flush()
    audit.log(
        db, user.id, "stock_adjust", "stock_item", item.id,
        {"before": before, "after": item.current_qty, "delta": delta, "reason": data.reason, "movement_id": mv.id},
    )
    db.commit()
    return get_item(db, item.id)


def _consume_lots(db: Session, item_id: int, qty: float) -> None:
    """FEFO: removes qty from the lots that expire first (best effort)."""
    remaining = qty
    lots = db.scalars(
        select(StockLot)
        .where(StockLot.stock_item_id == item_id, StockLot.qty_remaining > 0)
        .order_by(StockLot.expiry_date.is_(None), StockLot.expiry_date, StockLot.id)
    )
    for lot in lots:
        if remaining <= 0:
            break
        take = min(lot.qty_remaining, remaining)
        lot.qty_remaining = round(lot.qty_remaining - take, 4)
        remaining -= take


def waste(db: Session, data: WasteIn, user: User) -> StockItemOut:
    item = _usable_item(db, data.stock_item_id)
    mv = apply_movement(db, item.id, -data.qty, "waste", reason=data.reason, user_id=user.id)
    if item.track_expiry:
        _consume_lots(db, item.id, data.qty)
    db.flush()
    audit.log(
        db, user.id, "stock_waste", "stock_item", item.id,
        {"qty": data.qty, "reason": data.reason, "value_cents": round(data.qty * item.avg_cost_cents), "movement_id": mv.id},
    )
    db.commit()
    return get_item(db, item.id)


# ---------------------------------------------------------------- counts
def _count_out(db: Session, c: InventoryCount, with_items: bool = True) -> CountOut:
    stock = {s.id: s for s in db.scalars(select(StockItem).where(StockItem.id.in_([i.stock_item_id for i in c.items])))}
    cats, _ = _lookups(db)
    user_name = db.scalar(select(User.name).where(User.id == c.user_id)) if c.user_id else None
    items: list[CountItemOut] = []
    total_diff = 0
    counted = 0
    for ci in c.items:
        si = stock.get(ci.stock_item_id)
        cost = si.avg_cost_cents if si else 0
        diff = None if ci.counted_qty is None else round(ci.counted_qty - ci.expected_qty, 4)
        diff_val = None if diff is None else round(diff * cost)
        if diff_val is not None:
            total_diff += diff_val
            counted += 1
        items.append(
            CountItemOut(
                id=ci.id,
                stock_item_id=ci.stock_item_id,
                name=si.name if si else "?",
                unit=si.unit if si else "u",
                category_id=si.category_id if si else None,
                category_name=cats.get(si.category_id) if si and si.category_id else None,
                expected_qty=ci.expected_qty,
                counted_qty=ci.counted_qty,
                diff_qty=diff,
                diff_value_cents=diff_val,
                avg_cost_cents=cost,
            )
        )
    items.sort(key=lambda i: ((i.category_name or "~"), i.name))
    return CountOut(
        id=c.id, status=c.status, notes=c.notes, user_id=c.user_id, user_name=user_name,
        created_at=c.created_at, updated_at=c.updated_at, total_items=len(c.items), counted_items=counted,
        diff_value_cents=total_diff, items=items if with_items else [],
    )


def _get_count(db: Session, count_id: int) -> InventoryCount:
    c = db.get(InventoryCount, count_id)
    if not c:
        raise HTTPException(404, "Conteo no encontrado")
    return c


def list_counts(db: Session) -> list[CountOut]:
    return [
        _count_out(db, c, with_items=False)
        for c in db.scalars(select(InventoryCount).order_by(InventoryCount.created_at.desc(), InventoryCount.id.desc()))
    ]


def get_count(db: Session, count_id: int) -> CountOut:
    return _count_out(db, _get_count(db, count_id))


def create_count(db: Session, data: CountCreate, user: User) -> CountOut:
    q = select(StockItem).where(StockItem.active.is_(True)).order_by(StockItem.name)
    if data.category_id is not None:
        q = q.where(StockItem.category_id == data.category_id)
    usable = free_plan.active_ids(db, "stock_items")
    items = [i for i in db.scalars(q) if usable is None or i.id in usable]  # locked ones aren't counted
    if not items:
        raise HTTPException(400, "No hay insumos para contar")
    c = InventoryCount(status="open", notes=data.notes, user_id=user.id)
    c.items = [InventoryCountItem(stock_item_id=i.id, expected_qty=i.current_qty) for i in items]
    db.add(c)
    db.flush()
    audit.log(db, user.id, "create", "inventory_count", c.id, {"category_id": data.category_id, "items": len(items)})
    db.commit()
    return _count_out(db, c)


def _open_count(db: Session, count_id: int) -> InventoryCount:
    c = _get_count(db, count_id)
    if c.status != "open":
        raise HTTPException(409, "El conteo ya no está abierto")
    return c


def set_counted(db: Session, count_id: int, item_id: int, counted_qty: float | None) -> CountOut:
    c = _open_count(db, count_id)
    ci = next((i for i in c.items if i.id == item_id), None)
    if ci is None:
        raise HTTPException(404, "Ítem de conteo no encontrado")
    free_plan.ensure_all_usable(db, "stock_items", [ci.stock_item_id])
    ci.counted_qty = counted_qty
    c.updated_at = utcnow()
    db.commit()
    return _count_out(db, c)


def set_counted_bulk(db: Session, count_id: int, rows: list[CountItemRow]) -> CountOut:
    c = _open_count(db, count_id)
    by_id = {i.id: i for i in c.items}
    for r in rows:
        ci = by_id.get(r.id)
        if ci is None:
            raise HTTPException(404, "Ítem de conteo no encontrado")
        if r.counted_qty is not None:
            free_plan.ensure_all_usable(db, "stock_items", [ci.stock_item_id])
        ci.counted_qty = r.counted_qty
    c.updated_at = utcnow()
    db.commit()
    return _count_out(db, c)


def apply_count(db: Session, count_id: int, user: User) -> CountOut:
    """Sets each counted item to the counted qty via 'count' movements (diff vs current stock)."""
    c = _open_count(db, count_id)
    if not any(ci.counted_qty is not None for ci in c.items):
        raise HTTPException(400, "No cargaste ninguna cantidad contada")
    applied = []
    usable = free_plan.active_ids(db, "stock_items")
    for ci in c.items:
        if ci.counted_qty is None or (usable is not None and ci.stock_item_id not in usable):
            continue  # not counted, or locked by the free plan since the count started
        item = db.get(StockItem, ci.stock_item_id)
        if item is None:
            continue
        diff = round(ci.counted_qty - item.current_qty, 4)
        if abs(diff) < 1e-9:
            continue
        apply_movement(
            db, item.id, diff, "count", ref_type="inventory_count", ref_id=c.id,
            reason=f"Conteo físico #{c.id}", user_id=user.id,
        )
        applied.append({"stock_item_id": item.id, "diff": diff})
    c.status = "applied"
    audit.log(db, user.id, "count_apply", "inventory_count", c.id, {"adjustments": applied})
    db.commit()
    return _count_out(db, c)


def cancel_count(db: Session, count_id: int, user: User) -> CountOut:
    c = _open_count(db, count_id)
    c.status = "cancelled"
    audit.log(db, user.id, "cancel", "inventory_count", c.id)
    db.commit()
    return _count_out(db, c)


# ---------------------------------------------------------------- summary & suggestions
def summary(db: Session) -> StockSummary:
    items = list(db.scalars(select(StockItem).where(StockItem.active.is_(True))))
    statuses = [item_status(i) for i in items]
    return StockSummary(
        total_value_cents=sum(item_value_cents(i) for i in items),
        low_count=statuses.count("low"),
        out_count=statuses.count("out"),
        item_count=len(items),
    )


def daily_consumption(db: Session, days: int = SUGGESTION_DAYS) -> dict[int, float]:
    since = utcnow() - timedelta(days=days)
    rows = db.execute(
        select(StockMovement.stock_item_id, func.sum(StockMovement.qty))
        .where(StockMovement.ts >= since, StockMovement.type.in_(CONSUMPTION_TYPES))
        .group_by(StockMovement.stock_item_id)
    ).all()
    return {sid: max(0.0, -(total or 0)) / days for sid, total in rows}


def round_suggested(qty: float, unit: str) -> float:
    if qty <= 0:
        return 0
    if unit == "u":
        return float(math.ceil(qty))
    step = 100 if qty >= 1000 else 10
    return float(math.ceil(qty / step) * step)


def suggestions(db: Session, supplier_id: int | None = None) -> list[SuggestionGroup]:
    cons = daily_consumption(db)
    _, sups = _lookups(db)
    groups: dict[int | None, list[SuggestionItem]] = defaultdict(list)
    for item in db.scalars(select(StockItem).where(StockItem.active.is_(True)).order_by(StockItem.name)):
        status = item_status(item)
        if status == "ok":
            continue
        daily = cons.get(item.id, 0.0)
        cur = item.current_qty
        raw = max(item.min_qty * 2 - cur, daily * 7 - cur)
        qty = round_suggested(raw, item.unit)
        if qty <= 0:
            continue
        groups[item.default_supplier_id].append(
            SuggestionItem(
                stock_item_id=item.id, name=item.name, unit=item.unit, current_qty=cur, min_qty=item.min_qty,
                status=status, daily_consumption=round(daily, 3), suggested_qty=qty,
                avg_cost_cents=item.avg_cost_cents, est_cost_cents=round(qty * item.avg_cost_cents),
            )
        )
    out = [
        SuggestionGroup(
            supplier_id=sid,
            supplier_name=sups.get(sid, "Sin proveedor") if sid else "Sin proveedor",
            items=items,
            total_est_cents=sum(i.est_cost_cents for i in items),
        )
        for sid, items in groups.items()
    ]
    if supplier_id is not None:
        out = [g for g in out if g.supplier_id == supplier_id]
    out.sort(key=lambda g: (g.supplier_id is None, g.supplier_name))
    return out
