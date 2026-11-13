"""Customer queries, metrics, account payments and manual loyalty adjustments."""

import re
from datetime import timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session

from app.db import like_contains
from app.models import (
    CashMovement,
    CashSession,
    Customer,
    CustomerAccountMovement,
    LoyaltyTransaction,
    Sale,
    SaleItem,
    SalePayment,
    User,
    utcnow,
)
from app.services import audit, free_plan, idempotency, roles
from app.services.timeutil import day_bounds_utc, local_today, to_local

SEGMENTS = ("frecuentes", "inactivos", "cumpleanos_mes", "deudores")
ORDERS = ("name", "last_visit", "total_spent", "balance", "points", "recent")
FREQUENT_MIN_VISITS = 4
WINDOW_DAYS = 30


def get_or_404(db: Session, customer_id: int) -> Customer:
    c = db.get(Customer, customer_id)
    if c is None:
        raise HTTPException(404, "Cliente no encontrado")
    return c


def _completed():
    # Purchases only: courtesies (on the house) aren't spending nor loyalty activity.
    return and_(Sale.status == "completed", Sale.is_courtesy.is_(False))


# ---------------------------------------------------------------- listing


def _list_query(q: str | None, segment: str | None, include_inactive: bool) -> Select[Any]:
    since = utcnow() - timedelta(days=WINDOW_DAYS)
    totals = (
        select(
            Sale.customer_id.label("cid"),
            func.max(Sale.ts).label("last_visit_at"),
            func.count(Sale.id).label("visits"),
            func.coalesce(func.sum(Sale.total_cents), 0).label("spent"),
        )
        .where(_completed(), Sale.customer_id.is_not(None))
        .group_by(Sale.customer_id)
        .subquery()
    )
    recent = (
        select(Sale.customer_id.label("cid"), func.count(Sale.id).label("n30"))
        .where(_completed(), Sale.customer_id.is_not(None), Sale.ts >= since)
        .group_by(Sale.customer_id)
        .subquery()
    )
    stmt = (
        select(
            Customer,
            totals.c.last_visit_at,
            func.coalesce(totals.c.visits, 0).label("visits"),
            func.coalesce(totals.c.spent, 0).label("spent"),
            func.coalesce(recent.c.n30, 0).label("n30"),
        )
        .outerjoin(totals, totals.c.cid == Customer.id)
        .outerjoin(recent, recent.c.cid == Customer.id)
    )
    if not include_inactive:
        stmt = stmt.where(Customer.active.is_(True))
    if q and q.strip():
        term = q.strip()
        conds = [like_contains(Customer.name, term), like_contains(Customer.phone, term), like_contains(Customer.email, term)]
        digits = re.sub(r"\D", "", q)
        if len(digits) >= 3:
            phone_digits = func.replace(func.replace(func.replace(Customer.phone, " ", ""), "-", ""), "+", "")
            conds.append(phone_digits.like(f"%{digits}%"))
        stmt = stmt.where(or_(*conds))
    if segment == "frecuentes":
        stmt = stmt.where(func.coalesce(recent.c.n30, 0) >= FREQUENT_MIN_VISITS)
    elif segment == "inactivos":
        stmt = stmt.where(totals.c.visits > 0, totals.c.last_visit_at < since)
    elif segment == "cumpleanos_mes":
        month = f"{local_today().month:02d}"
        stmt = stmt.where(Customer.birthday.is_not(None), func.strftime("%m", Customer.birthday) == month)
    elif segment == "deudores":
        stmt = stmt.where(Customer.balance_cents > 0)
    return stmt


def _order(stmt: Select[Any], order: str | None) -> Select[Any]:
    cols = stmt.selected_columns
    match order:
        case "last_visit":
            return stmt.order_by(cols.last_visit_at.desc().nulls_last(), Customer.name)
        case "total_spent":
            return stmt.order_by(cols.spent.desc(), Customer.name)
        case "balance":
            return stmt.order_by(Customer.balance_cents.desc(), Customer.name)
        case "points":
            return stmt.order_by(Customer.points.desc(), Customer.name)
        case "recent":
            return stmt.order_by(Customer.created_at.desc())
        case _:
            return stmt.order_by(Customer.name)


def list_customers(
    db: Session,
    q: str | None = None,
    segment: str | None = None,
    order: str | None = None,
    include_inactive: bool = False,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    if segment and segment not in SEGMENTS:
        raise HTTPException(400, "Segmento inválido")
    stmt = _order(_list_query(q, segment, include_inactive), order)
    if limit is None:
        limit = 20 if q else 1000
    stmt = stmt.limit(limit)
    out = []
    usable = free_plan.active_ids(db, "customers")
    for c, last, visits, spent, n30 in db.execute(stmt).all():
        out.append(
            {
                **_base(c),
                "locked": bool(c.active and usable is not None and c.id not in usable),
                "last_visit_at": last,
                "visits": int(visits or 0),
                "visits_30d": int(n30 or 0),
                "total_spent_cents": int(spent or 0),
            }
        )
    return out


def _base(c: Customer) -> dict[str, Any]:
    return {
        k: getattr(c, k)
        for k in (
            "id", "name", "phone", "email", "birthday", "notes", "points",
            "balance_cents", "credit_limit_cents", "active", "created_at",
        )
    }


# ---------------------------------------------------------------- create / update


def _clean(data: dict[str, Any]) -> dict[str, Any]:
    for k in ("phone", "email", "notes"):
        if k in data and isinstance(data[k], str):
            data[k] = data[k].strip() or None
    if isinstance(data.get("name"), str):
        data["name"] = data["name"].strip()
        if not data["name"]:
            raise HTTPException(400, "El nombre es obligatorio")
    return data


def create(db: Session, data: dict[str, Any], user: User) -> Customer:
    data = _clean(data)
    if data.get("credit_limit_cents") and not roles.has(user, "customers.manage"):
        data["credit_limit_cents"] = 0
    if data.get("phone"):
        dup = db.scalar(select(Customer).where(Customer.phone == data["phone"], Customer.active.is_(True)))
        if dup:
            raise HTTPException(409, f"Ya existe un cliente con ese teléfono: {dup.name}")
    c = Customer(**data)
    db.add(c)
    db.flush()
    free_plan.on_created(db, "customers", c.id)
    audit.log(db, user.id, "create", "customer", c.id, {"name": c.name})
    db.commit()
    db.refresh(c)
    return c


def update(db: Session, c: Customer, data: dict[str, Any], user: User) -> Customer:
    data = _clean(data)
    is_manager = roles.has(user, "customers.manage")
    if "credit_limit_cents" in data and data["credit_limit_cents"] != c.credit_limit_cents and not is_manager:
        raise HTTPException(403, "Solo un encargado puede cambiar el límite de cuenta corriente")
    if "active" in data and data["active"] is False and not is_manager:
        raise HTTPException(403, "Solo un encargado puede desactivar clientes")
    if c.active and set(data) - {"active"}:
        free_plan.ensure_usable(db, "customers", c.id, c.name)  # locked: only archiving
    if data.get("active") is False and c.active:
        free_plan.on_archived(db, "customers", c.id)
    elif data.get("active") is True and not c.active:
        free_plan.on_reactivated(db, "customers", c.id)
    for k, v in data.items():
        setattr(c, k, v)
    audit.log(db, user.id, "update", "customer", c.id, {k: str(v) for k, v in data.items()})
    db.commit()
    db.refresh(c)
    return c


def deactivate(db: Session, c: Customer, user: User) -> None:
    if c.active:
        free_plan.on_archived(db, "customers", c.id)
    c.active = False
    audit.log(db, user.id, "deactivate", "customer", c.id, {"name": c.name})
    db.commit()


# ---------------------------------------------------------------- detail


def metrics(db: Session, customer_id: int) -> dict[str, Any]:
    row = db.execute(
        select(
            func.coalesce(func.sum(Sale.total_cents), 0),
            func.count(Sale.id),
            func.min(Sale.ts),
            func.max(Sale.ts),
        ).where(Sale.customer_id == customer_id, _completed())
    ).one()
    spent, tickets, first, last = int(row[0] or 0), int(row[1] or 0), row[2], row[3]
    since = utcnow() - timedelta(days=WINDOW_DAYS)
    visits_30d = db.scalar(
        select(func.count(Sale.id)).where(Sale.customer_id == customer_id, _completed(), Sale.ts >= since)
    ) or 0
    days_since = (local_today() - to_local(last).date()).days if last else None
    per_month = 0.0
    if first and tickets:
        span_days = max((utcnow() - first).days, 0)
        months = max(span_days / 30.44, 1.0)
        per_month = round(tickets / months, 1)
    top = _top_products(db, customer_id, 5)
    return {
        "total_spent_cents": spent,
        "tickets": tickets,
        "avg_ticket_cents": round(spent / tickets) if tickets else 0,
        "first_visit_at": first,
        "last_visit_at": last,
        "days_since_last_visit": days_since,
        "visits_per_month": per_month,
        "visits_30d": int(visits_30d),
        "favorite_product": top[0] if top else None,
        "top_products": top,
    }


def _top_products(db: Session, customer_id: int, limit: int) -> list[dict[str, Any]]:
    qty = func.sum(SaleItem.qty).label("qty")
    rows = db.execute(
        select(func.max(SaleItem.product_id), SaleItem.name_snapshot, qty)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(Sale.customer_id == customer_id, _completed())
        .group_by(SaleItem.name_snapshot)
        .order_by(qty.desc(), SaleItem.name_snapshot)
        .limit(limit)
    ).all()
    return [{"product_id": pid, "name": name, "qty": float(q or 0)} for pid, name, q in rows]


def detail(db: Session, c: Customer) -> dict[str, Any]:
    movements = list(
        db.scalars(
            select(CustomerAccountMovement)
            .where(CustomerAccountMovement.customer_id == c.id)
            .order_by(CustomerAccountMovement.ts.desc(), CustomerAccountMovement.id.desc())
            .limit(100)
        )
    )
    loyalty = list(
        db.scalars(
            select(LoyaltyTransaction)
            .where(LoyaltyTransaction.customer_id == c.id)
            .order_by(LoyaltyTransaction.ts.desc(), LoyaltyTransaction.id.desc())
            .limit(100)
        )
    )
    return {
        **_base(c),
        "locked": c.active and free_plan.is_locked(db, "customers", c.id),
        "metrics": metrics(db, c.id),
        "account_movements": movements,
        "loyalty_transactions": loyalty,
        "over_limit": c.balance_cents > 0 and c.balance_cents > c.credit_limit_cents,
    }


def sales_page(db: Session, customer_id: int, page: int, page_size: int) -> dict[str, Any]:
    base = select(Sale).where(Sale.customer_id == customer_id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    sales = list(
        db.scalars(base.order_by(Sale.ts.desc(), Sale.id.desc()).offset((page - 1) * page_size).limit(page_size))
    )
    ids = [s.id for s in sales]
    items_by_sale: dict[int, list[SaleItem]] = {}
    pays_by_sale: dict[int, list[str]] = {}
    if ids:
        for it in db.scalars(select(SaleItem).where(SaleItem.sale_id.in_(ids)).order_by(SaleItem.id)):
            items_by_sale.setdefault(it.sale_id, []).append(it)
        for p in db.scalars(select(SalePayment).where(SalePayment.sale_id.in_(ids))):
            pays_by_sale.setdefault(p.sale_id, [])
            if p.method not in pays_by_sale[p.sale_id]:
                pays_by_sale[p.sale_id].append(p.method)
    out = []
    for s in sales:
        its = items_by_sale.get(s.id, [])
        summary = ", ".join(f"{_fmt_qty(i.qty)}× {i.name_snapshot}" for i in its[:4])
        if len(its) > 4:
            summary += f" y {len(its) - 4} más"
        out.append(
            {
                "id": s.id,
                "number": s.number,
                "ts": s.ts,
                "total_cents": s.total_cents,
                "status": s.status,
                "channel": s.channel,
                "items_count": sum(i.qty for i in its),
                "items_summary": summary,
                "payment_methods": pays_by_sale.get(s.id, []),
            }
        )
    return {"items": out, "total": int(total), "page": page, "page_size": page_size}


def _fmt_qty(q: float) -> str:
    return str(int(q)) if float(q).is_integer() else f"{q:g}"


# ---------------------------------------------------------------- account & points


def register_payment_once(db: Session, c: Customer, amount_cents: int, method: str, user: User, key: str | None) -> tuple[CustomerAccountMovement, bool]:
    """`register_payment` that survives being sent twice (see services/idempotency). Second value True = a repeat."""
    if key is None:
        return register_payment(db, c, amount_cents, method, user), False
    h = idempotency.body_hash({"customer_id": c.id, "amount_cents": amount_cents, "method": method})
    done = idempotency.find(db, key, "account_payment", user, h)
    if done is not None:
        db.rollback()
        return db.get(CustomerAccountMovement, done), True
    mv = register_payment(db, c, amount_cents, method, user, _key=(key, h))
    return mv, False


def register_payment(db: Session, c: Customer, amount_cents: int, method: str, user: User, _key: tuple[str, str] | None = None) -> CustomerAccountMovement:
    if amount_cents <= 0:
        raise HTTPException(400, "El monto debe ser mayor a cero")
    if c.balance_cents <= 0:
        raise HTTPException(400, "El cliente no tiene deuda en cuenta corriente")
    if amount_cents > c.balance_cents:
        raise HTTPException(400, "El pago supera la deuda del cliente")
    if method == "cuenta_corriente":
        raise HTTPException(400, "Medio de pago inválido")
    mv = CustomerAccountMovement(
        customer_id=c.id, amount_cents=-amount_cents, type="payment", method=method, user_id=user.id
    )
    db.add(mv)
    c.balance_cents -= amount_cents
    if method == "efectivo":
        # Cash enters the drawer: record it in the open cash session, if any.
        session = db.scalar(select(CashSession).where(CashSession.status == "open").order_by(CashSession.id.desc()))
        if session:
            db.add(
                CashMovement(
                    session_id=session.id,
                    type="in",
                    amount_cents=amount_cents,
                    reason=f"Pago cuenta corriente: {c.name}",
                    user_id=user.id,
                )
            )
    db.flush()
    audit.log(db, user.id, "payment", "customer", c.id, {"amount_cents": amount_cents, "method": method})
    if _key:
        idempotency.record(db, _key[0], "account_payment", user, _key[1], mv.id)
    db.commit()
    db.refresh(mv)
    return mv


def adjust_points(db: Session, c: Customer, points: int, reason: str, user: User) -> LoyaltyTransaction:
    free_plan.ensure_usable(db, "customers", c.id, c.name)
    if points == 0:
        raise HTTPException(400, "Indicá una cantidad de puntos distinta de cero")
    if c.points + points < 0:
        raise HTTPException(400, f"El cliente tiene {c.points} puntos; no puede quedar en negativo")
    tx = LoyaltyTransaction(customer_id=c.id, points=points, reason=reason.strip() or "Ajuste manual")
    db.add(tx)
    c.points += points
    db.flush()
    audit.log(db, user.id, "points_adjust", "customer", c.id, {"points": points, "reason": reason})
    db.commit()
    db.refresh(tx)
    return tx


# ---------------------------------------------------------------- stats


def birthdays_today(db: Session) -> list[Customer]:
    today = local_today()
    md = f"{today.month:02d}-{today.day:02d}"
    return list(
        db.scalars(
            select(Customer)
            .where(
                Customer.active.is_(True),
                Customer.birthday.is_not(None),
                func.strftime("%m-%d", Customer.birthday) == md,
            )
            .order_by(Customer.name)
        )
    )


def stats(db: Session) -> dict[str, Any]:
    active = Customer.active.is_(True)
    total = db.scalar(select(func.count(Customer.id)).where(active)) or 0
    since = utcnow() - timedelta(days=WINDOW_DAYS)
    activos = db.scalar(
        select(func.count(func.distinct(Sale.customer_id))).where(
            _completed(), Sale.customer_id.is_not(None), Sale.ts >= since
        )
    ) or 0
    month_start = day_bounds_utc(local_today().replace(day=1))[0]
    nuevos = db.scalar(select(func.count(Customer.id)).where(active, Customer.created_at >= month_start)) or 0
    deuda, deudores = db.execute(
        select(func.coalesce(func.sum(Customer.balance_cents), 0), func.count(Customer.id)).where(
            Customer.balance_cents > 0
        )
    ).one()
    return {
        "total": int(total),
        "activos_30d": int(activos),
        "nuevos_mes": int(nuevos),
        "deuda_total_cents": int(deuda or 0),
        "deudores": int(deudores or 0),
        "cumpleanos_hoy": [{"id": c.id, "name": c.name, "phone": c.phone} for c in birthdays_today(db)],
    }
