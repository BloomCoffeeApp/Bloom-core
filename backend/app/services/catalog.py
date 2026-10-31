"""Catalog business logic: products with recipes, modifiers, prices and the POS catalog."""

from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import (
    Modifier,
    ModifierGroup,
    ModifierRecipeItem,
    PriceHistory,
    Product,
    ProductCategory,
    ProductModifierGroup,
    RecipeItem,
    StockItem,
    User,
)
from app.schemas.catalog import (
    BulkPriceIn,
    BulkPriceOut,
    BulkPriceRow,
    CategoryIn,
    CategoryOut,
    CategoryRef,
    CategoryUpdate,
    ModifierGroupIn,
    ModifierGroupOut,
    ModifierGroupUpdate,
    ModifierIn,
    ModifierOut,
    ModifierRecipeItemOut,
    PosCatalogOut,
    PosCategory,
    PosModifier,
    PosModifierGroup,
    PosProduct,
    PriceHistoryOut,
    ProductIn,
    ProductOut,
    ProductUpdate,
    RecipeItemOut,
)
from app.services import audit


# ---------------------------------------------------------------- helpers
def margin_pct(price_cents: int, cost_cents: int) -> float | None:
    if price_cents <= 0:
        return None
    return round((price_cents - cost_cents) / price_cents * 100, 1)


def round_price(cents: float, round_to: int) -> int:
    """Rounds to the nearest multiple of round_to (half up). round_to <= 0 → nearest cent."""
    if round_to <= 0:
        return int(round(cents))
    return int((cents + round_to / 2) // round_to * round_to)


def _get_product(db: Session, product_id: int) -> Product:
    p = db.get(Product, product_id)
    if not p:
        raise HTTPException(404, "Producto no encontrado")
    return p


def _check_stock_items(db: Session, ids: list[int]) -> None:
    ids = list(set(ids))
    if not ids:
        return
    found = set(db.scalars(select(StockItem.id).where(StockItem.id.in_(ids))))
    if missing := set(ids) - found:
        raise HTTPException(400, f"Insumo inexistente: {sorted(missing)}")


def _check_groups(db: Session, ids: list[int]) -> None:
    ids = list(set(ids))
    if not ids:
        return
    found = set(db.scalars(select(ModifierGroup.id).where(ModifierGroup.id.in_(ids))))
    if missing := set(ids) - found:
        raise HTTPException(400, f"Grupo de modificadores inexistente: {sorted(missing)}")


def _check_category(db: Session, category_id: int | None) -> None:
    if category_id is not None and not db.get(ProductCategory, category_id):
        raise HTTPException(400, "Categoría inexistente")


def _product_group_ids(db: Session, product_ids: list[int]) -> dict[int, list[int]]:
    out: dict[int, list[int]] = defaultdict(list)
    if not product_ids:
        return out
    rows = db.execute(
        select(ProductModifierGroup.product_id, ProductModifierGroup.group_id).where(
            ProductModifierGroup.product_id.in_(product_ids)
        )
    )
    for pid, gid in rows:
        out[pid].append(gid)
    return out


def product_out(
    db: Session,
    p: Product,
    *,
    categories: dict[int, ProductCategory] | None = None,
    stock: dict[int, StockItem] | None = None,
    group_ids: dict[int, list[int]] | None = None,
) -> ProductOut:
    if categories is None:
        cat = db.get(ProductCategory, p.category_id) if p.category_id else None
    else:
        cat = categories.get(p.category_id) if p.category_id else None
    if stock is None:
        sids = [ri.stock_item_id for ri in p.recipe_items] + ([p.stock_item_id] if p.stock_item_id else [])
        stock = {s.id: s for s in db.scalars(select(StockItem).where(StockItem.id.in_(sids)))} if sids else {}
    if group_ids is None:
        group_ids = _product_group_ids(db, [p.id])

    lines: list[RecipeItemOut] = []
    total = 0.0
    if p.stock_item_id and (si := stock.get(p.stock_item_id)):
        total += si.avg_cost_cents
    for ri in p.recipe_items:
        si = stock.get(ri.stock_item_id)
        unit_cost = si.avg_cost_cents if si else 0.0
        line = ri.qty * unit_cost
        total += line
        lines.append(
            RecipeItemOut(
                id=ri.id,
                stock_item_id=ri.stock_item_id,
                stock_item_name=si.name if si else "?",
                unit=si.unit if si else "u",
                qty=ri.qty,
                unit_cost_cents=unit_cost,
                line_cost_cents=round(line, 2),
            )
        )
    cost = round(total)
    direct = stock.get(p.stock_item_id) if p.stock_item_id else None
    return ProductOut(
        id=p.id,
        name=p.name,
        category_id=p.category_id,
        category=CategoryRef.model_validate(cat) if cat else None,
        description=p.description,
        price_cents=p.price_cents,
        image_path=p.image_path,
        color=p.color,
        active=p.active,
        show_in_pos=p.show_in_pos,
        stock_item_id=p.stock_item_id,
        stock_item_name=direct.name if direct else None,
        sort_order=p.sort_order,
        cost_cents=cost,
        margin_pct=margin_pct(p.price_cents, cost),
        recipe_items=lines,
        modifier_group_ids=sorted(group_ids.get(p.id, [])),
        updated_at=p.updated_at,
    )


# ---------------------------------------------------------------- categories
def list_categories(db: Session, include_inactive: bool = True) -> list[CategoryOut]:
    q = select(ProductCategory).order_by(ProductCategory.sort_order, ProductCategory.name)
    if not include_inactive:
        q = q.where(ProductCategory.active.is_(True))
    counts = dict(
        db.execute(
            select(Product.category_id, func.count(Product.id))
            .where(Product.active.is_(True))
            .group_by(Product.category_id)
        ).all()
    )
    out = []
    for c in db.scalars(q):
        o = CategoryOut.model_validate(c)
        o.product_count = counts.get(c.id, 0)
        out.append(o)
    return out


def create_category(db: Session, data: CategoryIn, user: User) -> ProductCategory:
    c = ProductCategory(**data.model_dump())
    db.add(c)
    db.flush()
    audit.log(db, user.id, "create", "product_category", c.id, {"name": c.name})
    db.commit()
    return c


def update_category(db: Session, category_id: int, data: CategoryUpdate, user: User) -> ProductCategory:
    c = db.get(ProductCategory, category_id)
    if not c:
        raise HTTPException(404, "Categoría no encontrada")
    changes = data.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(c, k, v)
    audit.log(db, user.id, "update", "product_category", c.id, changes)
    db.commit()
    return c


# ---------------------------------------------------------------- products
def list_products(
    db: Session, *, category_id: int | None = None, include_inactive: bool = False, q: str | None = None
) -> list[ProductOut]:
    query = select(Product).order_by(Product.sort_order, Product.name)
    if not include_inactive:
        query = query.where(Product.active.is_(True))
    if category_id is not None:
        query = query.where(Product.category_id == category_id)
    if q:
        query = query.where(Product.name.ilike(f"%{q}%"))
    products = list(db.scalars(query))
    categories = {c.id: c for c in db.scalars(select(ProductCategory))}
    stock = {s.id: s for s in db.scalars(select(StockItem))}
    groups = _product_group_ids(db, [p.id for p in products])
    return [product_out(db, p, categories=categories, stock=stock, group_ids=groups) for p in products]


def get_product(db: Session, product_id: int) -> ProductOut:
    return product_out(db, _get_product(db, product_id))


def _set_recipe(db: Session, p: Product, items: list) -> None:
    _check_stock_items(db, [i.stock_item_id for i in items])
    merged: dict[int, float] = defaultdict(float)
    for i in items:
        merged[i.stock_item_id] += i.qty
    p.recipe_items.clear()
    db.flush()
    p.recipe_items.extend(RecipeItem(stock_item_id=sid, qty=qty) for sid, qty in merged.items())


def _set_groups(db: Session, product_id: int, group_ids: list[int]) -> None:
    _check_groups(db, group_ids)
    db.execute(delete(ProductModifierGroup).where(ProductModifierGroup.product_id == product_id))
    for gid in dict.fromkeys(group_ids):
        db.add(ProductModifierGroup(product_id=product_id, group_id=gid))


def create_product(db: Session, data: ProductIn, user: User) -> ProductOut:
    _check_category(db, data.category_id)
    if data.stock_item_id:
        _check_stock_items(db, [data.stock_item_id])
    fields = data.model_dump(exclude={"recipe_items", "modifier_group_ids"})
    p = Product(**fields)
    db.add(p)
    db.flush()
    _set_recipe(db, p, data.recipe_items)
    _set_groups(db, p.id, data.modifier_group_ids)
    audit.log(db, user.id, "create", "product", p.id, {"name": p.name, "price_cents": p.price_cents})
    db.commit()
    db.refresh(p)
    return product_out(db, p)


def update_product(db: Session, product_id: int, data: ProductUpdate, user: User) -> ProductOut:
    p = _get_product(db, product_id)
    changes = data.model_dump(exclude_unset=True, exclude={"recipe_items", "modifier_group_ids"})
    if "category_id" in changes:
        _check_category(db, changes["category_id"])
    if changes.get("stock_item_id"):
        _check_stock_items(db, [changes["stock_item_id"]])
    new_price = changes.get("price_cents")
    if new_price is not None and new_price != p.price_cents:
        db.add(PriceHistory(product_id=p.id, old_cents=p.price_cents, new_cents=new_price, user_id=user.id))
        audit.log(db, user.id, "price_change", "product", p.id, {"old_cents": p.price_cents, "new_cents": new_price})
    for k, v in changes.items():
        setattr(p, k, v)
    if data.recipe_items is not None:
        _set_recipe(db, p, data.recipe_items)
        changes["recipe_items"] = [i.model_dump() for i in data.recipe_items]
    if data.modifier_group_ids is not None:
        _set_groups(db, p.id, data.modifier_group_ids)
        changes["modifier_group_ids"] = data.modifier_group_ids
    audit.log(db, user.id, "update", "product", p.id, changes)
    db.commit()
    db.refresh(p)
    return product_out(db, p)


def deactivate_product(db: Session, product_id: int, user: User) -> None:
    p = _get_product(db, product_id)
    p.active = False
    audit.log(db, user.id, "deactivate", "product", p.id, {"name": p.name})
    db.commit()


def bulk_price(db: Session, data: BulkPriceIn, user: User) -> BulkPriceOut:
    q = select(Product).where(Product.active.is_(True)).order_by(Product.sort_order, Product.name)
    if data.category_id is not None:
        _check_category(db, data.category_id)
        q = q.where(Product.category_id == data.category_id)
    factor = 1 + data.percent / 100
    rows: list[BulkPriceRow] = []
    for p in db.scalars(q):
        new = max(0, round_price(p.price_cents * factor, data.round_to_cents))
        rows.append(BulkPriceRow(product_id=p.id, name=p.name, category_id=p.category_id, old_cents=p.price_cents, new_cents=new))
        if not data.dry_run and new != p.price_cents:
            db.add(PriceHistory(product_id=p.id, old_cents=p.price_cents, new_cents=new, user_id=user.id))
            p.price_cents = new
    if not data.dry_run:
        audit.log(
            db,
            user.id,
            "bulk_price",
            "product",
            None,
            {
                "category_id": data.category_id,
                "percent": data.percent,
                "round_to_cents": data.round_to_cents,
                "count": sum(1 for r in rows if r.old_cents != r.new_cents),
            },
        )
        db.commit()
    return BulkPriceOut(applied=not data.dry_run, count=len(rows), items=rows)


def price_history(db: Session, product_id: int) -> list[PriceHistoryOut]:
    _get_product(db, product_id)
    rows = db.execute(
        select(PriceHistory, User.name)
        .outerjoin(User, User.id == PriceHistory.user_id)
        .where(PriceHistory.product_id == product_id)
        .order_by(PriceHistory.ts.desc(), PriceHistory.id.desc())
    ).all()
    return [
        PriceHistoryOut(
            id=h.id,
            product_id=h.product_id,
            old_cents=h.old_cents,
            new_cents=h.new_cents,
            change_pct=round((h.new_cents - h.old_cents) / h.old_cents * 100, 1) if h.old_cents else None,
            user_id=h.user_id,
            user_name=name,
            ts=h.ts,
        )
        for h, name in rows
    ]


# ---------------------------------------------------------------- modifier groups
def _group_out(db: Session, g: ModifierGroup, stock: dict[int, StockItem], product_ids: list[int]) -> ModifierGroupOut:
    mods = []
    for m in sorted(g.modifiers, key=lambda m: (m.sort_order, m.id)):
        mods.append(
            ModifierOut(
                id=m.id,
                name=m.name,
                price_delta_cents=m.price_delta_cents,
                sort_order=m.sort_order,
                recipe_items=[
                    ModifierRecipeItemOut(
                        id=r.id,
                        stock_item_id=r.stock_item_id,
                        stock_item_name=stock[r.stock_item_id].name if r.stock_item_id in stock else "?",
                        unit=stock[r.stock_item_id].unit if r.stock_item_id in stock else "u",
                        qty_delta=r.qty_delta,
                    )
                    for r in m.recipe_items
                ],
            )
        )
    return ModifierGroupOut(
        id=g.id, name=g.name, min_select=g.min_select, max_select=g.max_select, modifiers=mods, product_ids=product_ids
    )


def list_groups(db: Session) -> list[ModifierGroupOut]:
    stock = {s.id: s for s in db.scalars(select(StockItem))}
    links: dict[int, list[int]] = defaultdict(list)
    for pid, gid in db.execute(select(ProductModifierGroup.product_id, ProductModifierGroup.group_id)):
        links[gid].append(pid)
    return [_group_out(db, g, stock, sorted(links[g.id])) for g in db.scalars(select(ModifierGroup).order_by(ModifierGroup.name))]


def _get_group_out(db: Session, g: ModifierGroup) -> ModifierGroupOut:
    stock = {s.id: s for s in db.scalars(select(StockItem))}
    pids = list(db.scalars(select(ProductModifierGroup.product_id).where(ProductModifierGroup.group_id == g.id)))
    return _group_out(db, g, stock, sorted(pids))


def _validate_group(min_select: int, max_select: int) -> None:
    if min_select > max_select:
        raise HTTPException(400, "El mínimo no puede superar al máximo")


def _apply_modifiers(db: Session, g: ModifierGroup, items: list[ModifierIn]) -> None:
    _check_stock_items(db, [r.stock_item_id for m in items for r in m.recipe_items])
    existing = {m.id: m for m in g.modifiers}
    keep: set[int] = set()
    for idx, data in enumerate(items):
        m = existing.get(data.id) if data.id else None
        if m is None:
            m = Modifier(name=data.name)
            g.modifiers.append(m)
        else:
            keep.add(m.id)
        m.name = data.name
        m.price_delta_cents = data.price_delta_cents
        m.sort_order = data.sort_order if data.sort_order else idx
        m.recipe_items.clear()
        m.recipe_items.extend(ModifierRecipeItem(stock_item_id=r.stock_item_id, qty_delta=r.qty_delta) for r in data.recipe_items)
    for mid, m in existing.items():
        if mid not in keep:
            g.modifiers.remove(m)


def create_group(db: Session, data: ModifierGroupIn, user: User) -> ModifierGroupOut:
    _validate_group(data.min_select, data.max_select)
    g = ModifierGroup(name=data.name, min_select=data.min_select, max_select=data.max_select)
    db.add(g)
    _apply_modifiers(db, g, data.modifiers)
    db.flush()
    audit.log(db, user.id, "create", "modifier_group", g.id, {"name": g.name})
    db.commit()
    db.refresh(g)
    return _get_group_out(db, g)


def update_group(db: Session, group_id: int, data: ModifierGroupUpdate, user: User) -> ModifierGroupOut:
    g = db.get(ModifierGroup, group_id)
    if not g:
        raise HTTPException(404, "Grupo no encontrado")
    changes = data.model_dump(exclude_unset=True, exclude={"modifiers"})
    for k, v in changes.items():
        setattr(g, k, v)
    _validate_group(g.min_select, g.max_select)
    if data.modifiers is not None:
        _apply_modifiers(db, g, data.modifiers)
        changes["modifiers"] = [m.name for m in data.modifiers]
    audit.log(db, user.id, "update", "modifier_group", g.id, changes)
    db.commit()
    db.refresh(g)
    return _get_group_out(db, g)


def delete_group(db: Session, group_id: int, user: User) -> None:
    g = db.get(ModifierGroup, group_id)
    if not g:
        raise HTTPException(404, "Grupo no encontrado")
    db.execute(delete(ProductModifierGroup).where(ProductModifierGroup.group_id == g.id))
    audit.log(db, user.id, "delete", "modifier_group", g.id, {"name": g.name})
    db.delete(g)
    db.commit()


# ---------------------------------------------------------------- POS
def pos_catalog(db: Session) -> PosCatalogOut:
    cats = list(
        db.scalars(
            select(ProductCategory)
            .where(ProductCategory.active.is_(True))
            .order_by(ProductCategory.sort_order, ProductCategory.name)
        )
    )
    active_cat_ids = {c.id for c in cats}
    products = [
        p
        for p in db.scalars(
            select(Product)
            .where(Product.active.is_(True), Product.show_in_pos.is_(True))
            .order_by(Product.sort_order, Product.name)
        )
        if p.category_id is None or p.category_id in active_cat_ids
    ]
    groups = {
        g.id: PosModifierGroup(
            id=g.id,
            name=g.name,
            min_select=g.min_select,
            max_select=g.max_select,
            modifiers=[
                PosModifier(id=m.id, name=m.name, price_delta_cents=m.price_delta_cents)
                for m in sorted(g.modifiers, key=lambda m: (m.sort_order, m.id))
            ],
        )
        for g in db.scalars(select(ModifierGroup))
    }
    links = _product_group_ids(db, [p.id for p in products])
    return PosCatalogOut(
        categories=[PosCategory(id=c.id, name=c.name, color=c.color, icon=c.icon) for c in cats],
        products=[
            PosProduct(
                id=p.id,
                name=p.name,
                price_cents=p.price_cents,
                category_id=p.category_id,
                color=p.color,
                image_path=p.image_path,
                modifier_groups=[groups[gid] for gid in sorted(links.get(p.id, [])) if gid in groups],
            )
            for p in products
        ],
    )

