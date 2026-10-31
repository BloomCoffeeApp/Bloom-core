"""Single entry point for every stock change. Never touch StockItem.current_qty elsewhere."""

from sqlalchemy.orm import Session

from app.models import StockItem, StockMovement


def weighted_avg_cost(current_qty: float, current_cost: float, in_qty: float, in_cost: float) -> float:
    if current_qty <= 0:
        return in_cost
    total = current_qty + in_qty
    if total <= 0:
        return in_cost
    return (current_qty * current_cost + in_qty * in_cost) / total


def apply_movement(
    db: Session,
    stock_item_id: int,
    qty: float,
    type: str,
    *,
    unit_cost_cents: float | None = None,
    ref_type: str | None = None,
    ref_id: int | None = None,
    reason: str | None = None,
    user_id: int | None = None,
) -> StockMovement:
    """Applies a signed qty to a stock item and records the movement (caller commits).

    Purchases (qty > 0 with a unit cost) update the weighted average cost.
    Stock is allowed to go negative; alerts flag it.
    """
    item = db.get(StockItem, stock_item_id)
    if item is None:
        raise ValueError(f"Insumo {stock_item_id} inexistente")
    if type == "purchase" and qty > 0 and unit_cost_cents is not None:
        item.avg_cost_cents = weighted_avg_cost(item.current_qty, item.avg_cost_cents, qty, unit_cost_cents)
    item.current_qty = round(item.current_qty + qty, 4)
    mv = StockMovement(
        stock_item_id=stock_item_id,
        type=type,
        qty=qty,
        unit_cost_cents=unit_cost_cents if unit_cost_cents is not None else item.avg_cost_cents,
        balance_after=item.current_qty,
        ref_type=ref_type,
        ref_id=ref_id,
        reason=reason,
        user_id=user_id,
    )
    db.add(mv)
    return mv
