"""Dashboard KPIs (and helpers shared with the Pro reports), computed with aggregated SQL over completed sales.

Local time grouping: the DB stores naive UTC. SQLite's ``strftime`` / ``date`` accept a
modifier like ``'-180 minutes'`` which we derive from ``timeutil.local_now().utcoffset()``.
America/Argentina/Buenos_Aires has no DST today (fixed UTC-03:00), so a constant shift is
exact. If DST ever returns, hour/day buckets near the switch would be off by one hour.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    CashMovement,
    CashSession,
    CashSessionCount,
    PaymentMethod,
    Product,
    ProductCategory,
    Purchase,
    Sale,
    SaleItem,
    SalePayment,
    StockItem,
    StockMovement,
    Supplier,
    User,
)
from app.models.stock import MOVEMENT_TYPES
from app.services import orders, recipes
from app.services.timeutil import day_bounds_utc, local_now, local_today, range_bounds_utc

_OFFSET_MIN = int((local_now().utcoffset() or timedelta(hours=-3)).total_seconds() // 60)
LOCAL_SHIFT = f"{_OFFSET_MIN:+d} minutes"

SALES_GROUPS = ("day", "week", "month", "hour", "weekday", "product", "category", "payment", "user", "channel")
CHANNEL_LABEL = {"salon": "Salón", "llevar": "Para llevar", "delivery": "Delivery"}
WEEKDAYS = ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
          "octubre", "noviembre", "diciembre"]
MOVEMENT_LABEL = {
    "purchase": "Compra", "sale": "Venta", "adjustment": "Ajuste", "waste": "Merma",
    "internal": "Consumo interno", "void": "Anulación", "count": "Conteo",
}


def can_see_costs(user: User) -> bool:
    from app.services import roles

    return roles.has(user, "reports.view")


# ---------------------------------------------------------------- helpers

def local_date_expr(col: Any) -> Any:
    return func.date(col, LOCAL_SHIFT)


def local_fmt_expr(fmt: str, col: Any) -> Any:
    return func.strftime(fmt, col, LOCAL_SHIFT)


def _completed(a: datetime, b: datetime) -> tuple[Any, ...]:
    """Revenue-bearing sales in [a, b): completed and not a courtesy (those add $0 and aren't tickets)."""
    return (Sale.status == "completed", Sale.is_courtesy.is_(False), Sale.ts >= a, Sale.ts < b)


def _pct(part: float | int | None, whole: float | int | None) -> float | None:
    if not whole:
        return None
    return round((part or 0) * 100 / whole, 1)


def _delta(cur: float | int | None, prev: float | int | None) -> float | None:
    if cur is None or not prev:
        return None
    return round((cur - prev) * 100 / abs(prev), 1)


def _item_total() -> Any:
    """Line total; falls back to qty × price − discount if total wasn't stored."""
    return case(
        (SaleItem.total_cents != 0, SaleItem.total_cents),
        else_=SaleItem.qty * SaleItem.unit_price_cents - SaleItem.discount_cents,
    )


def _row(key: Any, label: str, tickets: int, qty: float | None, sales: int, cost: int) -> dict[str, Any]:
    sales, cost = int(round(sales or 0)), int(round(cost or 0))
    margin = sales - cost
    return {
        "key": str(key) if key is not None else "",
        "label": label,
        "tickets": int(tickets or 0),
        "qty": round(float(qty), 2) if qty is not None else None,
        "sales_cents": sales,
        "cost_cents": cost,
        "margin_cents": margin,
        "margin_pct": _pct(margin, sales),
    }


def default_range(start: date | None, end: date | None) -> tuple[date, date]:
    today = local_today()
    end = end or start or today
    start = start or end
    if start > end:
        start, end = end, start
    return start, end


# ---------------------------------------------------------------- dashboard

def _kpis(db: Session, a: datetime, b: datetime) -> dict[str, Any]:
    tickets, sales, cost = db.execute(
        select(func.count(Sale.id), func.coalesce(func.sum(Sale.total_cents), 0),
               func.coalesce(func.sum(Sale.cost_cents), 0)).where(*_completed(a, b))
    ).one()
    margin = sales - cost
    return {
        "sales_cents": int(sales),
        "tickets": int(tickets),
        "avg_ticket_cents": int(round(sales / tickets)) if tickets else 0,
        "gross_margin_cents": int(margin),
        "margin_pct": _pct(margin, sales),
    }


def _hourly(db: Session, conds: list[Any]) -> dict[int, int]:
    h = local_fmt_expr("%H", Sale.ts)
    rows = db.execute(
        select(h, func.sum(Sale.total_cents)).where(Sale.status == "completed", Sale.is_courtesy.is_(False), *conds).group_by(h)
    ).all()
    return {int(k): int(v or 0) for k, v in rows}


def _mix(rows: list[tuple[Any, str, int]]) -> list[dict[str, Any]]:
    total = sum(r[2] for r in rows) or 0
    out = [{"key": str(k), "label": label, "sales_cents": int(v), "pct": _pct(v, total) or 0.0} for k, label, v in rows]
    return sorted(out, key=lambda r: -r["sales_cents"])


def dashboard(db: Session, start: date, end: date, show_costs: bool) -> dict[str, Any]:
    a, b = range_bounds_utc(start, end)
    ndays = (end - start).days + 1
    if ndays == 1:
        prev_start = prev_end = start - timedelta(days=7)
        compare_label = "mismo día de la semana anterior"
    else:
        prev_end = start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=ndays - 1)
        compare_label = "período anterior"
    pa, pb = range_bounds_utc(prev_start, prev_end)
    cur, prev = _kpis(db, a, b), _kpis(db, pa, pb)
    deltas = {k: _delta(cur[k], prev[k]) for k in ("sales_cents", "tickets", "avg_ticket_cents", "gross_margin_cents")}
    if not show_costs:
        for d in (cur, prev):
            d["gross_margin_cents"] = None
            d["margin_pct"] = None
        deltas["gross_margin_cents"] = None

    # Hourly: one day → that day vs avg of same weekday in the previous 4 weeks.
    # Several days → average per day in the period vs average per day over the 28 previous days.
    period = _hourly(db, [Sale.ts >= a, Sale.ts < b])
    if ndays == 1:
        bounds = [day_bounds_utc(start - timedelta(days=7 * i)) for i in range(1, 5)]
        ref = _hourly(db, [or_(*[(Sale.ts >= x) & (Sale.ts < y) for x, y in bounds])])
        ref_div, cur_div = 4, 1
    else:
        ra, rb = range_bounds_utc(start - timedelta(days=28), start - timedelta(days=1))
        ref = _hourly(db, [Sale.ts >= ra, Sale.ts < rb])
        ref_div, cur_div = 28, ndays
    hours = sorted(set(period) | set(ref))
    hourly = []
    if hours:
        for hh in range(hours[0], hours[-1] + 1):
            hourly.append({
                "hour": hh,
                "label": f"{hh:02d}:00",
                "sales_cents": int(round(period.get(hh, 0) / cur_div)),
                "avg_cents": int(round(ref.get(hh, 0) / ref_div)),
            })

    # Daily, last 30 days ending at `end`.
    d0 = end - timedelta(days=29)
    da, db_ = range_bounds_utc(d0, end)
    dexpr = local_date_expr(Sale.ts)
    by_day = {
        k: (int(t), int(s or 0))
        for k, t, s in db.execute(
            select(dexpr, func.count(Sale.id), func.sum(Sale.total_cents))
            .where(*_completed(da, db_)).group_by(dexpr)
        ).all()
    }
    daily = []
    for i in range(30):
        d = d0 + timedelta(days=i)
        t, s = by_day.get(d.isoformat(), (0, 0))
        daily.append({"date": d.isoformat(), "label": d.strftime("%d/%m"), "tickets": t, "sales_cents": s})

    # Top products
    names = dict(db.execute(select(Product.id, Product.name)).all())
    top_rows = db.execute(
        select(SaleItem.product_id, func.max(SaleItem.name_snapshot), func.sum(SaleItem.qty), func.sum(_item_total()))
        .join(Sale, Sale.id == SaleItem.sale_id).where(*_completed(a, b))
        .group_by(SaleItem.product_id).order_by(func.sum(_item_total()).desc()).limit(10)
    ).all()
    top_products = [
        {"product_id": pid, "name": names.get(pid) or snap, "qty": round(float(q or 0), 2), "sales_cents": int(s or 0),
         "sizes": []}
        for pid, snap, q, s in top_rows
    ]
    by_pid = {t["product_id"]: t for t in top_products if t["product_id"] is not None}
    if by_pid:
        for pid, size_id, sname, q, s in db.execute(
            select(SaleItem.product_id, SaleItem.size_id, func.max(SaleItem.size_name), func.sum(SaleItem.qty),
                   func.sum(_item_total()))
            .join(Sale, Sale.id == SaleItem.sale_id)
            .where(*_completed(a, b), SaleItem.product_id.in_(by_pid), SaleItem.size_id.is_not(None))
            .group_by(SaleItem.product_id, SaleItem.size_id).order_by(func.sum(_item_total()).desc())
        ).all():
            by_pid[pid]["sizes"].append(
                {"size_id": size_id, "name": sname or "", "qty": round(float(q or 0), 2), "sales_cents": int(s or 0)}
            )

    pm_names = dict(db.execute(select(PaymentMethod.code, PaymentMethod.name)).all())
    pay = db.execute(
        select(SalePayment.method, func.sum(SalePayment.amount_cents))
        .join(Sale, Sale.id == SalePayment.sale_id).where(*_completed(a, b)).group_by(SalePayment.method)
    ).all()
    payment_mix = _mix([(m, pm_names.get(m, m), v or 0) for m, v in pay])

    cat_names = dict(db.execute(select(ProductCategory.id, ProductCategory.name)).all())
    cats = db.execute(
        select(Product.category_id, func.sum(_item_total()))
        .select_from(SaleItem).join(Sale, Sale.id == SaleItem.sale_id)
        .outerjoin(Product, Product.id == SaleItem.product_id)
        .where(*_completed(a, b)).group_by(Product.category_id)
    ).all()
    category_mix = _mix([(c or 0, cat_names.get(c, "Sin categoría"), v or 0) for c, v in cats])

    ch = db.execute(
        select(Sale.channel, func.sum(Sale.total_cents)).where(*_completed(a, b)).group_by(Sale.channel)
    ).all()
    channel_mix = _mix([(c, CHANNEL_LABEL.get(c, c), v or 0) for c, v in ch])

    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "days": ndays,
        "show_costs": show_costs,
        "compare_from": prev_start.isoformat(),
        "compare_to": prev_end.isoformat(),
        "compare_label": compare_label,
        "kpis": cur,
        "previous": prev,
        "deltas": deltas,
        "hourly": hourly,
        "hourly_mode": "day" if ndays == 1 else "avg",
        "daily": daily,
        "top_products": top_products,
        "payment_mix": payment_mix,
        "category_mix": category_mix,
        "channel_mix": channel_mix,
        "recent_sales": recent_sales(db, 8, pm_names),
        "orders": orders.summary(db, start, end),
    }


def recent_sales(db: Session, limit: int, pm_names: dict[str, str] | None = None) -> list[dict[str, Any]]:
    pm_names = pm_names or dict(db.execute(select(PaymentMethod.code, PaymentMethod.name)).all())
    users = dict(db.execute(select(User.id, User.name)).all())
    sales = db.scalars(
        select(Sale).options(selectinload(Sale.items), selectinload(Sale.payments))
        .order_by(Sale.ts.desc(), Sale.id.desc()).limit(limit)
    ).all()
    return [
        {
            "id": s.id,
            "number": s.number,
            "ts": s.ts,
            "total_cents": s.total_cents,
            "status": s.status,
            "is_courtesy": s.is_courtesy,
            "courtesy_cents": s.courtesy_cents,
            "channel": s.channel,
            "user_name": users.get(s.user_id) if s.user_id else None,
            "items_count": round(sum(i.qty for i in s.items), 2),
            "payment_methods": [pm_names.get(p.method, p.method) for p in s.payments],
        }
        for s in sales
    ]
