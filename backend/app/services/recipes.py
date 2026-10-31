"""Recipe expansion and costing shared by catalog, POS and reports."""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Modifier, ModifierRecipeItem, Product, RecipeItem, StockItem


def consumption(db: Session, product: Product, modifier_ids: list[int] | None = None) -> dict[int, float]:
    """Stock consumed by ONE unit of product (+ modifiers): {stock_item_id: qty}."""
    out: dict[int, float] = defaultdict(float)
    if product.stock_item_id:
        out[product.stock_item_id] += 1
    for ri in db.scalars(select(RecipeItem).where(RecipeItem.product_id == product.id)):
        out[ri.stock_item_id] += ri.qty
    if modifier_ids:
        rows = db.scalars(select(ModifierRecipeItem).where(ModifierRecipeItem.modifier_id.in_(modifier_ids)))
        for mri in rows:
            out[mri.stock_item_id] += mri.qty_delta
    return {k: v for k, v in out.items() if abs(v) > 1e-9}


def cost_cents(db: Session, product: Product, modifier_ids: list[int] | None = None) -> int:
    total = 0.0
    for sid, qty in consumption(db, product, modifier_ids).items():
        item = db.get(StockItem, sid)
        if item:
            total += qty * item.avg_cost_cents
    return round(total)


def modifiers_price_delta(db: Session, modifier_ids: list[int]) -> int:
    if not modifier_ids:
        return 0
    return sum(m.price_delta_cents for m in db.scalars(select(Modifier).where(Modifier.id.in_(modifier_ids))))
