"""Recipe expansion and costing shared by catalog, POS and reports.

Sizes: a ProductSize scales the product's base recipe (incl. a resale stock item) by `recipe_scale`
and then applies its overrides (`ProductSizeRecipeItem.qty` REPLACES the scaled qty of that stock
item; 0 removes it; an item not in the base recipe is added). Modifier recipe deltas (e.g. "leche de
avena": −200 ml entera, +200 ml avena) are scaled by the same factor, so they follow the size.
"""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Modifier, ModifierRecipeItem, Product, ProductSize, RecipeItem, StockItem


def base_recipe(db: Session, product: Product) -> dict[int, float]:
    out: dict[int, float] = defaultdict(float)
    if product.stock_item_id:
        out[product.stock_item_id] += 1
    for ri in db.scalars(select(RecipeItem).where(RecipeItem.product_id == product.id)):
        out[ri.stock_item_id] += ri.qty
    return dict(out)


def size_recipe(base: dict[int, float], scale: float, overrides: dict[int, float]) -> dict[int, float]:
    """Effective recipe of one size from the base recipe (pure: used for previews too)."""
    out = {sid: qty * scale for sid, qty in base.items()}
    out.update(overrides)
    return {k: v for k, v in out.items() if abs(v) > 1e-9}


def consumption(
    db: Session, product: Product, modifier_ids: list[int] | None = None, size: ProductSize | None = None
) -> dict[int, float]:
    """Stock consumed by ONE unit of product (+ size + modifiers): {stock_item_id: qty}."""
    base = base_recipe(db, product)
    scale = 1.0
    if size is not None:
        scale = size.recipe_scale or 1.0
        out: dict[int, float] = defaultdict(
            float, size_recipe(base, scale, {o.stock_item_id: o.qty for o in size.recipe_items})
        )
    else:
        out = defaultdict(float, base)
    if modifier_ids:
        rows = db.scalars(select(ModifierRecipeItem).where(ModifierRecipeItem.modifier_id.in_(modifier_ids)))
        for mri in rows:
            out[mri.stock_item_id] += mri.qty_delta * scale
    return {k: v for k, v in out.items() if abs(v) > 1e-9}


def cost_cents(
    db: Session, product: Product, modifier_ids: list[int] | None = None, size: ProductSize | None = None
) -> int:
    total = 0.0
    for sid, qty in consumption(db, product, modifier_ids, size).items():
        item = db.get(StockItem, sid)
        if item:
            total += qty * item.avg_cost_cents
    return round(total)


def default_size(product: Product) -> ProductSize | None:
    """The size preselected in the POS (the flagged one, else the first by size order)."""
    if not product.sizes:
        return None
    ordered = sorted(product.sizes, key=lambda ps: (ps.size.sort_order, ps.size.volume_ml or 0, ps.size_id))
    return next((ps for ps in ordered if ps.is_default), ordered[0])


def modifiers_price_delta(db: Session, modifier_ids: list[int]) -> int:
    if not modifier_ids:
        return 0
    return sum(m.price_delta_cents for m in db.scalars(select(Modifier).where(Modifier.id.in_(modifier_ids))))
