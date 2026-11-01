"""Sales: atomic checkout (stock, loyalty, cuenta corriente), listing, detail, void and ticket data."""

from collections import defaultdict
from datetime import date
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Customer,
    CustomerAccountMovement,
    LoyaltyTransaction,
    Modifier,
    ModifierGroup,
    PaymentMethod,
    Product,
    ProductModifierGroup,
    ProductSize,
    Sale,
    SaleItem,
    SalePayment,
    StockMovement,
    TableTab,
    User,
    utcnow,
)
from app.schemas.sales import PaymentMethodUpdate, SaleIn
from app.services import audit, orders, recipes, settings, stock
from app.services.orders import close_tab, tab_label
from app.services.cash import CASH, method_names, require_open_session, user_names
from app.services.timeutil import range_bounds_utc

CC = "cuenta_corriente"
DISCOUNT_ROLES = ("admin", "encargado")


def can_discount(user: User) -> bool:
    return user.role in DISCOUNT_ROLES


def loyalty_cfg(db: Session) -> dict[str, Any]:
    cfg = settings.get(db, "loyalty") or {}
    return {
        "enabled": bool(cfg.get("enabled", True)),
        "pesos_per_point": int(cfg.get("pesos_per_point") or 0),
        "points_per_reward": int(cfg.get("points_per_reward") or 0),
        "reward_value_cents": int(cfg.get("reward_value_cents") or 0),
    }


def points_for(total_cents: int, cfg: dict[str, Any]) -> int:
    """1 point every `pesos_per_point` pesos (default: 1 point each $1000)."""
    if not cfg["enabled"] or cfg["pesos_per_point"] <= 0 or total_cents <= 0:
        return 0
    return total_cents // (cfg["pesos_per_point"] * 100)


def points_discount_cents(points: int, cfg: dict[str, Any]) -> int:
    if cfg["points_per_reward"] <= 0:
        return 0
    return (points // cfg["points_per_reward"]) * cfg["reward_value_cents"]


def list_payment_methods(db: Session, include_inactive: bool = False) -> list[PaymentMethod]:
    q = select(PaymentMethod).order_by(PaymentMethod.sort_order)
    if not include_inactive:
        q = q.where(PaymentMethod.active.is_(True))
    return list(db.scalars(q))


def update_payment_method(db: Session, method_id: int, data: PaymentMethodUpdate, user: User) -> PaymentMethod:
    pm = db.get(PaymentMethod, method_id)
    if not pm:
        raise HTTPException(404, "Medio de pago no encontrado")
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    if changes.get("active") is False and pm.active:
        others = db.scalar(
            select(func.count(PaymentMethod.id)).where(PaymentMethod.active.is_(True), PaymentMethod.id != pm.id)
        )
        if not others:
            raise HTTPException(400, "Tiene que quedar al menos un medio de pago habilitado")
    if "name" in changes:
        changes["name"] = changes["name"].strip()
    for k, v in changes.items():
        setattr(pm, k, v)
    audit.log(db, user.id, "update", "payment_method", pm.id, changes)
    db.commit()
    return pm


def next_number(db: Session) -> int:
    return int(db.scalar(select(func.max(Sale.number))) or 0) + 1


def create_sale(db: Session, data: SaleIn, user: User) -> Sale:
    try:
        sale = _create_sale(db, data, user)
        db.commit()
        return sale
    except Exception:
        db.rollback()
        raise


def _create_sale(db: Session, data: SaleIn, user: User) -> Sale:
    session = require_open_session(db)
    courtesy = data.is_courtesy

    wants_discount = data.discount_cents > 0 or (data.discount_pct or 0) > 0 or any(i.discount_cents > 0 for i in data.items)
    if courtesy:
        # On the house: any cashier can do it (it's audited), but nothing else about money applies.
        if wants_discount:
            raise HTTPException(400, "Una cortesía no lleva descuentos")
        if data.points_to_redeem:
            raise HTTPException(400, "Una cortesía no permite canjear puntos")
        if any(p.amount_cents > 0 for p in data.payments):
            raise HTTPException(400, "Una cortesía no se cobra: sacá los pagos")
    elif wants_discount and not can_discount(user):
        raise HTTPException(403, "Solo un encargado o administrador puede aplicar descuentos")

    tab = _open_tab(db, data.tab_id) if data.tab_id is not None else None
    ctx = LineContext(db, data.items)

    # --- Lines ---
    lines: list[SaleItem] = []
    consumption: dict[int, float] = defaultdict(float)
    subtotal = 0
    cost_total = 0
    courtesy_value = 0
    for it in data.items:
        p, size, mods = ctx.check(it.product_id, it.size_id, it.modifier_ids)
        mod_ids = [m.id for m in mods]
        unit = unit_price(p, size, mods)
        gross = round(unit * it.qty)
        if it.discount_cents > gross:
            raise HTTPException(400, f"El descuento de {p.name} supera su importe")
        line_total = gross - it.discount_cents
        # Courtesy lines keep the list price but are fully discounted, so every revenue sum sees 0.
        line_discount = gross if courtesy else it.discount_cents
        if courtesy:
            line_total = 0
        courtesy_value += gross if courtesy else 0
        unit_cost = recipes.cost_cents(db, p, mod_ids, size)
        line_cost = round(unit_cost * it.qty)
        for sid, q in recipes.consumption(db, p, mod_ids, size).items():
            consumption[sid] += q * it.qty
        subtotal += line_total
        cost_total += line_cost
        lines.append(
            SaleItem(
                product_id=p.id,
                name_snapshot=p.name,
                size_id=size.size_id if size else None,
                size_name=size.size.name if size else None,
                qty=it.qty,
                unit_price_cents=unit,
                discount_cents=line_discount,
                total_cents=line_total,
                cost_cents=line_cost,
                modifiers=[{"id": m.id, "name": m.name, "price_delta_cents": m.price_delta_cents} for m in mods] or None,
                notes=(it.notes or "").strip() or None,
            )
        )

    # --- Discounts ---
    if data.discount_pct:
        discount = round(subtotal * data.discount_pct / 100)
    else:
        discount = data.discount_cents
    if discount > subtotal:
        raise HTTPException(400, "El descuento supera el subtotal")

    # --- Customer & loyalty ---
    customer: Customer | None = None
    if data.customer_id is not None:
        customer = db.get(Customer, data.customer_id)
        if customer is None or not customer.active:
            raise HTTPException(400, "Cliente inexistente o inactivo")
    cfg = loyalty_cfg(db)
    points_redeemed = data.points_to_redeem
    points_disc = 0
    if points_redeemed:
        if customer is None:
            raise HTTPException(400, "Para canjear puntos elegí un cliente")
        if not cfg["enabled"] or cfg["points_per_reward"] <= 0:
            raise HTTPException(400, "El programa de puntos está desactivado")
        if points_redeemed % cfg["points_per_reward"]:
            raise HTTPException(400, f"Los puntos se canjean de a {cfg['points_per_reward']}")
        if customer.points < points_redeemed:
            raise HTTPException(400, f"El cliente tiene solo {customer.points} puntos")
        points_disc = min(points_discount_cents(points_redeemed, cfg), subtotal - discount)

    total = subtotal - discount - points_disc

    # --- Payments ---
    active_methods = set(db.scalars(select(PaymentMethod.code).where(PaymentMethod.active.is_(True))))
    payments: list[SalePayment] = []
    paid = 0
    cc_amount = 0
    for pay in data.payments:
        if pay.amount_cents == 0:
            continue
        if pay.method not in active_methods:
            raise HTTPException(400, f"Medio de pago no habilitado: {pay.method}")
        change = 0
        tendered = None
        if pay.tendered_cents is not None:
            if pay.method != CASH:
                raise HTTPException(400, "El vuelto solo aplica a pagos en efectivo")
            if pay.tendered_cents < pay.amount_cents:
                raise HTTPException(400, "El monto entregado es menor al importe en efectivo")
            tendered = pay.tendered_cents
            change = tendered - pay.amount_cents
        if pay.method == CC:
            cc_amount += pay.amount_cents
        paid += pay.amount_cents
        payments.append(SalePayment(method=pay.method, amount_cents=pay.amount_cents, tendered_cents=tendered, change_cents=change))
    if paid != total:
        raise HTTPException(400, f"Los pagos ({paid / 100:.2f}) no coinciden con el total ({total / 100:.2f})")
    if cc_amount:
        if customer is None:
            raise HTTPException(400, "Para cobrar a cuenta corriente elegí un cliente")
        new_balance = customer.balance_cents + cc_amount
        if customer.credit_limit_cents > 0 and new_balance > customer.credit_limit_cents:
            available = max(customer.credit_limit_cents - customer.balance_cents, 0)
            raise HTTPException(400, f"Supera el límite de cuenta corriente (disponible ${available / 100:,.2f})")

    # --- Persist ---
    points_earned = points_for(total, cfg) if customer and not courtesy else 0
    sale = Sale(
        number=next_number(db),
        cash_session_id=session.id,
        user_id=user.id,
        customer_id=customer.id if customer else None,
        channel=data.channel,
        table_label=(data.table_label or "").strip() or None,
        subtotal_cents=subtotal,
        discount_cents=discount + points_disc,
        total_cents=total,
        cost_cents=cost_total,
        points_earned=points_earned,
        points_redeemed=points_redeemed,
        notes=(data.notes or "").strip() or None,
        status="completed",
        is_courtesy=courtesy,
        courtesy_cents=courtesy_value,
        courtesy_reason=((data.courtesy_reason or "").strip() or None) if courtesy else None,
    )
    sale.items = lines
    sale.payments = payments
    if tab is not None and not sale.table_label:
        sale.table_label = tab_label(db, tab)
    db.add(sale)
    db.flush()

    if tab is not None:
        close_tab(db, tab, sale)
    # Lines charged from a table's tab already went to the bar as that table's orders.
    orders.create_from_sale(db, sale, [it.to_bar for it in data.items], user)

    for sid, q in consumption.items():
        reason = f"Cortesía #{sale.number}" if courtesy else f"Venta #{sale.number}"
        stock.apply_movement(db, sid, -q, "sale", ref_type="sale", ref_id=sale.id, reason=reason, user_id=user.id)

    if customer:
        if points_redeemed:
            customer.points -= points_redeemed
            db.add(LoyaltyTransaction(customer_id=customer.id, points=-points_redeemed, reason=f"Canje en ticket #{sale.number}", sale_id=sale.id))
        if points_earned:
            customer.points += points_earned
            db.add(LoyaltyTransaction(customer_id=customer.id, points=points_earned, reason=f"Compra ticket #{sale.number}", sale_id=sale.id))
        if cc_amount:
            customer.balance_cents += cc_amount
            db.add(CustomerAccountMovement(customer_id=customer.id, amount_cents=cc_amount, type="charge", method=CC, sale_id=sale.id, user_id=user.id))

    if courtesy:
        audit.log(
            db, user.id, "courtesy", "sale", sale.id,
            {"number": sale.number, "courtesy_cents": courtesy_value, "reason": sale.courtesy_reason},
        )
    else:
        audit.log(db, user.id, "create", "sale", sale.id, {"number": sale.number, "total_cents": total})
    return sale


class LineContext:
    """Catalog loaded in bulk for a set of lines, plus the size/modifier rules every order line obeys
    (POS sales and customer orders from the table use the same checks)."""

    def __init__(self, db: Session, items: list[Any]) -> None:
        pids = {i.product_id for i in items}
        self.products = {
            p.id: p for p in db.scalars(select(Product).options(selectinload(Product.sizes)).where(Product.id.in_(pids)))
        }
        for pid in pids:
            p = self.products.get(pid)
            if p is None or not p.active:
                raise HTTPException(400, f"Producto {pid} inexistente o inactivo")
        self.allowed_groups: dict[int, set[int]] = defaultdict(set)
        for pmg in db.scalars(select(ProductModifierGroup).where(ProductModifierGroup.product_id.in_(pids))):
            self.allowed_groups[pmg.product_id].add(pmg.group_id)
        mod_ids = {m for i in items for m in i.modifier_ids}
        self.modifiers = {m.id: m for m in db.scalars(select(Modifier).where(Modifier.id.in_(mod_ids)))} if mod_ids else {}
        group_ids = {g for gs in self.allowed_groups.values() for g in gs}
        self.groups = (
            {g.id: g for g in db.scalars(select(ModifierGroup).where(ModifierGroup.id.in_(group_ids)))} if group_ids else {}
        )

    def check(self, product_id: int, size_id: int | None, modifier_ids: list[int]) -> tuple[Product, ProductSize | None, list[Modifier]]:
        p = self.products[product_id]
        size = _pick_size(p, size_id)
        mod_ids = list(dict.fromkeys(modifier_ids))
        per_group: dict[int, int] = defaultdict(int)
        for mid in mod_ids:
            m = self.modifiers.get(mid)
            if m is None or m.group_id not in self.allowed_groups[p.id]:
                raise HTTPException(400, f"Modificador {mid} no válido para {p.name}")
            per_group[m.group_id] += 1
        for gid in self.allowed_groups[p.id]:
            g = self.groups[gid]
            n = per_group.get(gid, 0)
            if n < g.min_select:
                raise HTTPException(400, f"{p.name}: elegí al menos {g.min_select} en «{g.name}»")
            if g.max_select > 0 and n > g.max_select:
                raise HTTPException(400, f"{p.name}: máximo {g.max_select} en «{g.name}»")
        return p, size, [self.modifiers[mid] for mid in mod_ids]


def unit_price(p: Product, size: ProductSize | None, mods: list[Modifier]) -> int:
    """Price now: the chosen size's price (or the product's) plus modifiers."""
    return (size.price_cents if size else p.price_cents) + sum(m.price_delta_cents for m in mods)


def _open_tab(db: Session, tab_id: int) -> TableTab:
    tab = db.get(TableTab, tab_id)
    if tab is None or tab.status != "open":
        raise HTTPException(409, "Esa mesa ya fue cobrada o no existe")
    return tab


def _pick_size(p: Product, size_id: int | None) -> ProductSize | None:
    """The ProductSize sold. Sized products need one (missing = the default); others must not get one."""
    if not p.sizes:
        if size_id is not None:
            raise HTTPException(400, f"{p.name} no se vende por tamaño")
        return None
    if size_id is None:
        size = recipes.default_size(p)
        if size is not None and not size.size.active:
            size = next((ps for ps in p.sizes if ps.size.active), None)
    else:
        size = next((ps for ps in p.sizes if ps.size_id == size_id), None)
        if size is None:
            raise HTTPException(400, f"Tamaño no válido para {p.name}")
    if size is None or not size.size.active:
        raise HTTPException(400, f"El tamaño elegido de {p.name} no está disponible")
    return size


def void_sale(db: Session, sale_id: int, reason: str, user: User) -> Sale:
    sale = db.get(Sale, sale_id)
    if sale is None:
        raise HTTPException(404, "Venta no encontrada")
    if sale.status == "voided":
        raise HTTPException(409, "La venta ya está anulada")
    try:
        # Stock: reverse the exact movements recorded for this sale; fall back to recipes.
        movements = list(
            db.scalars(select(StockMovement).where(StockMovement.ref_type == "sale", StockMovement.ref_id == sale.id, StockMovement.type == "sale"))
        )
        label = f"Anulación venta #{sale.number}"
        if movements:
            for mv in movements:
                stock.apply_movement(db, mv.stock_item_id, -mv.qty, "void", ref_type="sale", ref_id=sale.id, reason=label, user_id=user.id)
        else:
            back: dict[int, float] = defaultdict(float)
            for it in sale.items:
                p = db.get(Product, it.product_id) if it.product_id else None
                if p is None:
                    continue
                mids = [m["id"] for m in (it.modifiers or []) if "id" in m]
                size = next((ps for ps in p.sizes if ps.size_id == it.size_id), None) if it.size_id else None
                for sid, q in recipes.consumption(db, p, mids, size).items():
                    back[sid] += q * it.qty
            for sid, q in back.items():
                stock.apply_movement(db, sid, q, "void", ref_type="sale", ref_id=sale.id, reason=label, user_id=user.id)

        if sale.customer_id:
            customer = db.get(Customer, sale.customer_id)
            if customer:
                if sale.points_earned:
                    customer.points -= sale.points_earned
                    db.add(LoyaltyTransaction(customer_id=customer.id, points=-sale.points_earned, reason=label, sale_id=sale.id))
                if sale.points_redeemed:
                    customer.points += sale.points_redeemed
                    db.add(LoyaltyTransaction(customer_id=customer.id, points=sale.points_redeemed, reason=f"Reintegro de canje ({label.lower()})", sale_id=sale.id))
                cc = sum(p.amount_cents for p in sale.payments if p.method == CC)
                if cc:
                    customer.balance_cents -= cc
                    db.add(CustomerAccountMovement(customer_id=customer.id, amount_cents=-cc, type="void", method=CC, sale_id=sale.id, user_id=user.id))

        sale.status = "voided"
        sale.void_reason = reason.strip()
        sale.voided_by = user.id
        sale.voided_at = utcnow()
        audit.log(db, user.id, "void", "sale", sale.id, {"number": sale.number, "reason": reason})
        db.commit()
    except Exception:
        db.rollback()
        raise
    return sale


# ---------- Read side ----------


def _points_disc(sale: Sale, cfg: dict[str, Any]) -> int:
    if not sale.points_redeemed:
        return 0
    return min(points_discount_cents(sale.points_redeemed, cfg), sale.discount_cents)


def serialize(sale: Sale, unames: dict[int, str], cnames: dict[int, str], cfg: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": sale.id,
        "number": sale.number,
        "ts": sale.ts,
        "status": sale.status,
        "is_courtesy": sale.is_courtesy,
        "courtesy_cents": sale.courtesy_cents,
        "courtesy_reason": sale.courtesy_reason,
        "channel": sale.channel,
        "table_label": sale.table_label,
        "cash_session_id": sale.cash_session_id,
        "user_id": sale.user_id,
        "user_name": unames.get(sale.user_id) if sale.user_id else None,
        "customer_id": sale.customer_id,
        "customer_name": cnames.get(sale.customer_id) if sale.customer_id else None,
        "subtotal_cents": sale.subtotal_cents,
        "discount_cents": sale.discount_cents,
        "points_discount_cents": _points_disc(sale, cfg),
        "total_cents": sale.total_cents,
        "cost_cents": sale.cost_cents,
        "points_earned": sale.points_earned,
        "points_redeemed": sale.points_redeemed,
        "notes": sale.notes,
        "void_reason": sale.void_reason,
        "voided_by": sale.voided_by,
        "voided_by_name": unames.get(sale.voided_by) if sale.voided_by else None,
        "voided_at": sale.voided_at,
        "methods": list(dict.fromkeys(p.method for p in sale.payments)),
        "items_count": sum(i.qty for i in sale.items),
    }


def get_detail(db: Session, sale_id: int) -> dict[str, Any]:
    sale = db.get(Sale, sale_id)
    if sale is None:
        raise HTTPException(404, "Venta no encontrada")
    unames = user_names(db, {sale.user_id, sale.voided_by})
    customer = db.get(Customer, sale.customer_id) if sale.customer_id else None
    cnames = {customer.id: customer.name} if customer else {}
    out = serialize(sale, unames, cnames, loyalty_cfg(db))
    out["items"] = sale.items
    out["payments"] = sale.payments
    out["change_cents"] = sum(p.change_cents for p in sale.payments)
    out["customer"] = (
        {"id": customer.id, "name": customer.name, "phone": customer.phone, "points": customer.points, "balance_cents": customer.balance_cents}
        if customer
        else None
    )
    return out


def list_sales(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = None,
    user_id: int | None = None,
    customer_id: int | None = None,
    method: str | None = None,
    number: int | None = None,
    cash_session_id: int | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    conds = []
    if date_from or date_to:
        start, end = range_bounds_utc(date_from or date(2000, 1, 1), date_to or date(2100, 1, 1))
        conds += [Sale.ts >= start, Sale.ts < end]
    if status == "courtesy":  # pseudo-status for the list filter: completed courtesy sales
        conds += [Sale.status == "completed", Sale.is_courtesy.is_(True)]
    elif status:
        conds.append(Sale.status == status)
    if user_id:
        conds.append(Sale.user_id == user_id)
    if customer_id:
        conds.append(Sale.customer_id == customer_id)
    if number:
        conds.append(Sale.number == number)
    if cash_session_id:
        conds.append(Sale.cash_session_id == cash_session_id)
    if method:
        conds.append(Sale.id.in_(select(SalePayment.sale_id).where(SalePayment.method == method)))

    total = int(db.scalar(select(func.count(Sale.id)).where(*conds)) or 0)
    sum_total = int(
        db.scalar(select(func.coalesce(func.sum(Sale.total_cents), 0)).where(*conds, Sale.status == "completed")) or 0
    )
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    sales = list(
        db.scalars(select(Sale).options(selectinload(Sale.items), selectinload(Sale.payments)).where(*conds).order_by(Sale.number.desc()).limit(page_size).offset((page - 1) * page_size))
    )
    unames = user_names(db, {u for s in sales for u in (s.user_id, s.voided_by)})
    cids = {s.customer_id for s in sales if s.customer_id}
    cnames = {i: n for i, n in db.execute(select(Customer.id, Customer.name).where(Customer.id.in_(cids)))} if cids else {}
    cfg = loyalty_cfg(db)
    return {
        "items": [serialize(s, unames, cnames, cfg) for s in sales],
        "total": total,
        "page": page,
        "page_size": page_size,
        "sum_total_cents": sum_total,
    }


def ticket(db: Session, sale_id: int) -> dict[str, Any]:
    return {
        "business": settings.get(db, "business") or {},
        "sale": get_detail(db, sale_id),
        "payment_names": method_names(db),
    }
