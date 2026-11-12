"""Supplies by channel ("Insumos según el canal"): what a sold unit consumes depending on how it's served.

Data-driven and empty by default — nothing is preset; the café builds the lists:
- One full list per channel: `salon` (servilleta, sobre de azúcar…), `llevar` (vaso, tapa, manga…),
  `delivery` (vaso, tapa, bolsa, precinto…). Any stock item, any quantity per unit sold.
- Per size: rows with `size_id` override the base rows (size_id NULL) of the same channel for that
  size — the quantity REPLACES (0 = not used) and a new item is added (8 oz cup in the base list; the
  12 oz size: 8 oz cup → 0, 12 oz cup → 1). Same convention as the size recipe adjustments.
- A product without rows of its own uses its category's lists (category default); sizes are the
  business' shared size list, so a category can also have per-size rows.
The POS sale (counter "Para llevar" included), a charged table tab and online orders (their sale) add
this to the recipe consumption of the same sale, in the same transaction, through
`stock.apply_movement`; voiding the sale restores it (it reverses the sale's exact movements).
"""

from collections import defaultdict
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Product, ProductCategory, Size, StockItem, User
from app.models.channel_supplies import SUPPLY_CHANNELS, ChannelSupply
from app.services import audit


class SupplyRow(BaseModel):
    channel: str = Field(pattern=r"^(salon|llevar|delivery)$")
    size_id: int | None = None
    stock_item_id: int
    qty: float = Field(default=1, ge=0, le=1000)


class SuppliesIn(BaseModel):
    rows: list[SupplyRow] = Field(default_factory=list, max_length=300)


def _owner(product_id: int | None, category_id: int | None):
    if product_id is not None:
        return ChannelSupply.product_id == product_id
    return ChannelSupply.category_id == category_id


def _rows(db: Session, product_id: int | None = None, category_id: int | None = None) -> list[ChannelSupply]:
    return list(db.scalars(select(ChannelSupply).where(_owner(product_id, category_id)).order_by(ChannelSupply.id)))


def per_unit(rows: list[ChannelSupply], channel: str, size_id: int | None) -> dict[int, float]:
    """Stock item → quantity one unit consumes in this channel and size."""
    if channel not in SUPPLY_CHANNELS:
        return {}
    out: dict[int, float] = {}
    for r in rows:
        if r.channel == channel and r.size_id is None:
            out[r.stock_item_id] = r.qty
    if size_id is not None:
        for r in rows:
            if r.channel == channel and r.size_id == size_id:
                out[r.stock_item_id] = r.qty
    return {k: v for k, v in out.items() if v > 0}


def consumption(db: Session, channel: str, lines: list[tuple[Product, int | None, float]]) -> dict[int, float]:
    """Total extra consumption of (product, size_id, qty) lines sold through `channel`."""
    if channel not in SUPPLY_CHANNELS or not lines:
        return {}
    pids = {p.id for p, _, _ in lines}
    cids = {p.category_id for p, _, _ in lines if p.category_id is not None}
    by_product: dict[int, list[ChannelSupply]] = defaultdict(list)
    by_category: dict[int, list[ChannelSupply]] = defaultdict(list)
    q = select(ChannelSupply).where(ChannelSupply.product_id.in_(pids) | ChannelSupply.category_id.in_(cids or {-1}))
    for r in db.scalars(q):
        if r.product_id is not None:
            by_product[r.product_id].append(r)
        elif r.category_id is not None:
            by_category[r.category_id].append(r)
    total: dict[int, float] = defaultdict(float)
    for p, size_id, qty in lines:
        rows = by_product.get(p.id) or by_category.get(p.category_id if p.category_id is not None else -1, [])
        for sid, q_ in per_unit(rows, channel, size_id).items():
            total[sid] += q_ * qty
    return dict(total)


# ---------------------------------------------------------------- editor


def _out(db: Session, rows: list[ChannelSupply]) -> list[dict[str, Any]]:
    ids = {r.stock_item_id for r in rows}
    items = {s.id: s for s in db.scalars(select(StockItem).where(StockItem.id.in_(ids)))} if ids else {}
    return [
        {"id": r.id, "channel": r.channel, "size_id": r.size_id, "stock_item_id": r.stock_item_id, "qty": r.qty,
         "stock_item_name": items[r.stock_item_id].name if r.stock_item_id in items else "?",
         "unit": getattr(items.get(r.stock_item_id), "unit", None)}
        for r in rows
    ]


def get_product(db: Session, product_id: int) -> dict[str, Any]:
    p = db.get(Product, product_id)
    if p is None:
        raise HTTPException(404, "Producto no encontrado")
    own = _rows(db, product_id=p.id)
    cat = _rows(db, category_id=p.category_id) if p.category_id is not None else []
    category = db.get(ProductCategory, p.category_id) if p.category_id is not None else None
    return {"rows": _out(db, own), "inherited": not own and bool(cat), "category_rows": _out(db, cat),
            "category_id": p.category_id, "category_name": category.name if category else None}


def get_category(db: Session, category_id: int) -> dict[str, Any]:
    c = db.get(ProductCategory, category_id)
    if c is None:
        raise HTTPException(404, "Categoría no encontrada")
    return {"rows": _out(db, _rows(db, category_id=c.id)), "inherited": False, "category_rows": [],
            "category_id": c.id, "category_name": c.name}


def _validate(db: Session, rows: list[SupplyRow]) -> None:
    sids = {r.stock_item_id for r in rows}
    if sids - (set(db.scalars(select(StockItem.id).where(StockItem.id.in_(sids)))) if sids else set()):
        raise HTTPException(400, "Algún insumo no existe")
    sizes = {r.size_id for r in rows if r.size_id is not None}
    if sizes - (set(db.scalars(select(Size.id).where(Size.id.in_(sizes)))) if sizes else set()):
        raise HTTPException(400, "Algún tamaño no existe")
    seen = set()
    for r in rows:
        key = (r.channel, r.size_id, r.stock_item_id)
        if key in seen:
            raise HTTPException(400, "Hay un insumo repetido en la misma lista")
        seen.add(key)


def put(db: Session, user: User, data: SuppliesIn, product_id: int | None = None, category_id: int | None = None) -> dict[str, Any]:
    """Replaces every list of a product (empty = use its category's) or of a category."""
    if product_id is not None and db.get(Product, product_id) is None:
        raise HTTPException(404, "Producto no encontrado")
    if product_id is None and db.get(ProductCategory, category_id) is None:
        raise HTTPException(404, "Categoría no encontrada")
    _validate(db, data.rows)
    db.execute(delete(ChannelSupply).where(_owner(product_id, category_id)))
    for r in data.rows:
        db.add(ChannelSupply(product_id=product_id, category_id=category_id if product_id is None else None,
                             channel=r.channel, size_id=r.size_id, stock_item_id=r.stock_item_id, qty=r.qty))
    audit.log(db, user.id, "update", "channel_supplies", product_id or category_id,
              {"owner": "product" if product_id is not None else "category", "rows": len(data.rows)})
    db.commit()
    return get_product(db, product_id) if product_id is not None else get_category(db, category_id)  # type: ignore[arg-type]
