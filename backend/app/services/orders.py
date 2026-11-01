"""Order queue for the bar/kitchen screen: lifecycle, timers/late flags, open tabs per table and metrics.

Lifecycle: pending (a customer's order waiting for a waiter) → received → preparing → ready → delivered,
or cancelled. POS sales become `received` orders automatically (per channel and per category, see the
`orders` setting and `ProductCategory.send_to_orders`); they never move stock (the sale already did).

Timers start at `received_at` (when the order enters the bar queue). Target = the channel's target; with
Pro (`orders_pro`) = max over its items of (product prep minutes, or the channel's target when the product
has none). Late = prep time > target. Also Pro: stations (one order per station, same number, routed by
category) and the customer pickup screen.
`now()` is the single clock of this module so tests can freeze it.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.licensing import has_feature
from app.models import (
    DiningTable,
    Order,
    OrderItem,
    OrderStation,
    Product,
    ProductCategory,
    Sale,
    TableTab,
    User,
    WaiterCall,
    utcnow,
)
from app.models.sales import CHANNELS
from app.services import audit, settings
from app.services.timeutil import day_bounds_utc, local_today, range_bounds_utc, to_local

ACTIVE = ("pending", "received", "preparing", "ready")
IN_PROGRESS = ("received", "preparing")
TRANSITIONS: dict[str, set[str]] = {
    "pending": {"received", "cancelled"},
    "received": {"preparing", "ready", "cancelled"},
    "preparing": {"ready", "received", "cancelled"},  # back to received = undo "empezar"
    "ready": {"delivered", "preparing"},  # back to preparing = undo "listo"
    "delivered": {"ready"},  # undo "entregado"
    "cancelled": set(),
}
STATUS_LABEL = {
    "pending": "Por confirmar",
    "received": "Recibido",
    "preparing": "En preparación",
    "ready": "Listo",
    "delivered": "Entregado",
    "cancelled": "Cancelado",
}
CHANNEL_LABEL = {"salon": "Salón", "llevar": "Para llevar", "delivery": "Delivery"}
BOARD_HOURS = 12  # older unfinished orders drop off the screen (forgotten ones don't pile up forever)
DEFAULT_TARGET = 10


def now() -> datetime:
    return utcnow()


# ---------------------------------------------------------------- settings


def cfg(db: Session) -> dict[str, Any]:
    raw = settings.get(db, "orders") or {}
    base = settings.DEFAULTS["orders"]
    return {
        "enabled": bool(raw.get("enabled", base["enabled"])),
        "channels": {c: bool((raw.get("channels") or {}).get(c, base["channels"][c])) for c in CHANNELS},
        "targets": {c: int((raw.get("targets") or {}).get(c, base["targets"][c]) or DEFAULT_TARGET) for c in CHANNELS},
        "warn_pct": int(raw.get("warn_pct", base["warn_pct"]) or base["warn_pct"]),
    }


def save_cfg(db: Session, data: dict[str, Any], user: User) -> dict[str, Any]:
    settings.put(db, "orders", data)
    audit.log(db, user.id, "update", "setting", None, {"key": "orders"})
    db.commit()
    return cfg(db)


def pro() -> bool:
    return has_feature("orders_pro")


def order_target(prep_minutes: list[int | None], channel_default: int) -> int:
    """Max over items of their prep time (or the channel default when the product has none).
    Per-product times are Pro: without `orders_pro` every order gets the channel's target."""
    if not pro():
        return channel_default
    return max((p or channel_default for p in prep_minutes), default=channel_default)


# ---------------------------------------------------------------- stations (Pro)


def active_stations(db: Session) -> list[OrderStation]:
    if not pro():
        return []
    q = select(OrderStation).where(OrderStation.active.is_(True)).order_by(OrderStation.sort_order, OrderStation.id)
    return list(db.scalars(q))


def route_stations(db: Session, order: Order) -> list[Order]:
    """Splits an order into one order per station (same number), by the category of each item.
    Items of categories without (an active) station go to the first station. No-op without stations."""
    stations = active_stations(db)
    if not stations:
        return [order]
    ids = {st.id for st in stations}
    pids = {i.product_id for i in order.items if i.product_id}
    cat_station = (
        dict(
            db.execute(
                select(Product.id, ProductCategory.station_id)
                .join(ProductCategory, ProductCategory.id == Product.category_id)
                .where(Product.id.in_(pids))
            ).all()
        )
        if pids
        else {}
    )
    groups: dict[int, list[OrderItem]] = defaultdict(list)
    for item in order.items:
        st = cat_station.get(item.product_id)
        groups[st if st in ids else stations[0].id].append(item)
    order_ids = [st.id for st in stations if st.id in groups]
    order.station_id = order_ids[0]
    out = [order]
    target = cfg(db)["targets"].get(order.channel, DEFAULT_TARGET)
    for sid in order_ids[1:]:
        items = groups[sid]
        for it in items:
            order.items.remove(it)
        sibling = Order(
            number=order.number, source=order.source, status=order.status, channel=order.channel,
            table_id=order.table_id, table_label=order.table_label, tab_id=order.tab_id, station_id=sid,
            sale_id=order.sale_id, note=order.note, created_at=order.created_at, received_at=order.received_at,
            created_by=order.created_by, confirmed_by=order.confirmed_by, client_ip=order.client_ip,
            target_minutes=order_target([i.prep_minutes for i in items], target),
        )
        sibling.items = [
            OrderItem(product_id=i.product_id, name_snapshot=i.name_snapshot, size_id=i.size_id, size_name=i.size_name,
                      qty=i.qty, unit_price_cents=i.unit_price_cents, modifiers=i.modifiers, notes=i.notes,
                      prep_minutes=i.prep_minutes)
            for i in items
        ]
        db.add(sibling)
        out.append(sibling)
    order.target_minutes = order_target([i.prep_minutes for i in order.items], target)
    db.flush()
    return out


def next_number(db: Session) -> int:
    a, b = day_bounds_utc(local_today_at(now()))
    return int(db.scalar(select(func.max(Order.number)).where(Order.created_at >= a, Order.created_at < b)) or 0) + 1


def local_today_at(t: datetime) -> date:
    return to_local(t).date()


# ---------------------------------------------------------------- creation


def create_from_sale(db: Session, sale: Sale, to_bar: list[bool], user: User) -> Order | None:
    """Sends the bar-bound lines of a POS sale to the order screen (same transaction as the sale)."""
    c = cfg(db)
    if not c["enabled"] or not c["channels"].get(sale.channel, False):
        return None
    pids = {i.product_id for i in sale.items if i.product_id}
    products = {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(pids)))} if pids else {}
    skip_cats = set(db.scalars(select(ProductCategory.id).where(ProductCategory.send_to_orders.is_(False))))
    items: list[OrderItem] = []
    for line, send in zip(sale.items, to_bar, strict=False):
        p = products.get(line.product_id) if line.product_id else None
        if not send or p is None or (p.category_id in skip_cats):
            continue
        items.append(
            OrderItem(
                product_id=p.id,
                name_snapshot=line.name_snapshot,
                size_id=line.size_id,
                size_name=line.size_name,
                qty=line.qty,
                unit_price_cents=line.unit_price_cents,
                modifiers=line.modifiers,
                notes=line.notes,
                prep_minutes=p.prep_minutes,
            )
        )
    if not items:
        return None
    t = now()
    order = Order(
        number=next_number(db),
        source="pos",
        status="received",
        channel=sale.channel,
        table_label=sale.table_label,
        sale_id=sale.id,
        note=(sale.notes or "")[:200] or None,
        target_minutes=order_target([i.prep_minutes for i in items], c["targets"][sale.channel]),
        created_at=t,
        received_at=t,
        created_by=user.id,
    )
    order.items = items
    db.add(order)
    db.flush()
    route_stations(db, order)
    return order


# ---------------------------------------------------------------- lifecycle


def get_order(db: Session, order_id: int) -> Order:
    o = db.get(Order, order_id)
    if o is None:
        raise HTTPException(404, "Pedido no encontrado")
    return o


def set_status(db: Session, order_id: int, status: str, user: User, reason: str | None = None) -> Order:
    o = get_order(db, order_id)
    if status not in TRANSITIONS.get(o.status, set()):
        raise HTTPException(
            409, f"El pedido #{o.number} está «{STATUS_LABEL[o.status]}»: no se puede pasar a «{STATUS_LABEL.get(status, status)}»"
        )
    t = now()
    prev = o.status
    if status == "received":
        if prev == "pending":  # a waiter/cashier confirms a customer's order: it enters the bar queue now
            o.received_at = t
            o.confirmed_by = user.id
            if o.table_id is not None:
                o.tab_id = open_tab(db, o.table_id).id
            audit.log(db, user.id, "confirm", "order", o.id, {"number": o.number, "table": o.table_label})
            o.status = status
            route_stations(db, o)
        else:
            o.started_at = None
    elif status == "preparing":
        if prev == "ready":
            o.ready_at = None
        o.started_at = o.started_at or t
        o.prepared_by = o.prepared_by or user.id
    elif status == "ready":
        if prev == "delivered":
            o.delivered_at = None
        else:
            o.ready_at = t
            o.prepared_by = o.prepared_by or user.id
    elif status == "delivered":
        o.delivered_at = t
    elif status == "cancelled":
        o.cancelled_at = t
        o.cancel_reason = (reason or "").strip()[:200] or None
        audit.log(db, user.id, "cancel", "order", o.id, {"number": o.number, "from": prev, "reason": o.cancel_reason})
    o.status = status
    db.commit()
    return o


def timing(o: Order, t: datetime, warn_pct: int) -> dict[str, Any]:
    """Elapsed seconds and traffic-light level. The clock stops when the order is ready."""
    if o.received_at is None:  # waiting for confirmation: not on the bar's clock yet
        return {"elapsed_s": max(int((t - o.created_at).total_seconds()), 0), "late": False, "level": "pending"}
    end = o.ready_at or o.cancelled_at or t
    elapsed = max(int((end - o.received_at).total_seconds()), 0)
    target_s = o.target_minutes * 60
    late = elapsed > target_s
    level = "late" if late else "warn" if elapsed * 100 >= target_s * warn_pct else "ok"
    return {"elapsed_s": elapsed, "late": late, "level": level}


def _items_out(o: Order) -> list[dict[str, Any]]:
    return [
        {
            "id": i.id,
            "product_id": i.product_id,
            "name": i.name_snapshot,
            "size_name": i.size_name,
            "qty": i.qty,
            "modifiers": [m.get("name", "") for m in (i.modifiers or [])],
            "notes": i.notes,
        }
        for i in o.items
    ]


def serialize(o: Order, t: datetime, warn_pct: int, names: dict[int, str], sale_numbers: dict[int, int]) -> dict[str, Any]:
    return {
        "id": o.id,
        "number": o.number,
        "source": o.source,
        "status": o.status,
        "channel": o.channel,
        "table_id": o.table_id,
        "table_label": o.table_label,
        "station_id": o.station_id,
        "sale_id": o.sale_id,
        "sale_number": sale_numbers.get(o.sale_id) if o.sale_id else None,
        "note": o.note,
        "target_minutes": o.target_minutes,
        "created_at": o.created_at,
        "received_at": o.received_at,
        "started_at": o.started_at,
        "ready_at": o.ready_at,
        "prepared_by_name": names.get(o.prepared_by) if o.prepared_by else None,
        "items": _items_out(o),
        **timing(o, t, warn_pct),
    }


def _sort_key(row: dict[str, Any]) -> tuple:
    rank = {"pending": 0, "received": 1, "preparing": 1, "ready": 2}[row["status"]]
    if row["status"] in IN_PROGRESS:  # late first (most overdue on top), then oldest first
        overdue = row["elapsed_s"] - row["target_minutes"] * 60
        return (rank, 0 if row["late"] else 1, -overdue if row["late"] else 0, row["received_at"])
    return (rank, 0, 0, row["ready_at"] or row["created_at"])


def board(db: Session, station_id: int | None = None) -> dict[str, Any]:
    """Live screen. With a station, only its orders (plus customer orders waiting for confirmation,
    which any screen can confirm)."""
    t = now()
    c = cfg(db)
    since = t - timedelta(hours=BOARD_HOURS)
    q = select(Order).options(selectinload(Order.items)).where(Order.status.in_(ACTIVE), Order.created_at >= since)
    if station_id is not None:
        q = q.where((Order.station_id == station_id) | (Order.status == "pending"))
    rows = list(db.scalars(q.order_by(Order.id)))
    names = dict(db.execute(select(User.id, User.name)).all())
    sids = {o.sale_id for o in rows if o.sale_id}
    sale_numbers = dict(db.execute(select(Sale.id, Sale.number).where(Sale.id.in_(sids))).all()) if sids else {}
    orders = sorted((serialize(o, t, c["warn_pct"], names, sale_numbers) for o in rows), key=_sort_key)
    stations = active_stations(db)
    return {
        "server_time": t,
        "settings": c,
        "pro": pro(),
        "stations": [{"id": st.id, "name": st.name, "print_tickets": st.print_tickets} for st in stations],
        "orders": orders,
        "calls": active_calls(db, t),
        "late_count": sum(1 for o in orders if o["late"] and o["status"] in IN_PROGRESS),
    }


def pickup(db: Session) -> dict[str, Any]:
    """Customer pickup screen (TV): order numbers only. A number is "listo" when every (station) order
    with that number is ready or delivered and at least one is still waiting to be picked up."""
    t = now()
    rows = db.execute(
        select(Order.number, Order.status, Order.ready_at).where(
            Order.created_at >= t - timedelta(hours=BOARD_HOURS), Order.status.not_in(("cancelled", "pending"))
        )
    ).all()
    by_num: dict[int, list] = defaultdict(list)
    for n, st, ready_at in rows:
        by_num[n].append((st, ready_at))
    preparing, ready = [], []
    for n, sts in by_num.items():
        if any(st in IN_PROGRESS for st, _ in sts):
            preparing.append(n)
        elif any(st == "ready" for st, _ in sts):
            ready.append((max(r for st, r in sts if r is not None), n))
    business = settings.get(db, "business") or {}
    return {
        "business_name": str(business.get("name") or ""),
        "preparing": sorted(preparing),
        "ready": [n for _, n in sorted(ready, reverse=True)],  # most recent first
    }


# ---------------------------------------------------------------- waiter calls


def active_calls(db: Session, t: datetime | None = None) -> list[dict[str, Any]]:
    t = t or now()
    rows = db.execute(
        select(WaiterCall, DiningTable.label)
        .join(DiningTable, DiningTable.id == WaiterCall.table_id)
        .where(WaiterCall.resolved_at.is_(None), WaiterCall.expires_at > t)
        .order_by(WaiterCall.created_at)
    ).all()
    return [
        {
            "id": c.id,
            "table_id": c.table_id,
            "table_label": label,
            "kind": c.kind,
            "created_at": c.created_at,
            "elapsed_s": max(int((t - c.created_at).total_seconds()), 0),
        }
        for c, label in rows
    ]


def resolve_call(db: Session, call_id: int, user: User) -> None:
    call = db.get(WaiterCall, call_id)
    if call is None:
        raise HTTPException(404, "Llamado no encontrado")
    if call.resolved_at is None:
        call.resolved_at = now()
        call.resolved_by = user.id
        db.commit()


# ---------------------------------------------------------------- open tabs ("mesa abierta")


def open_tab(db: Session, table_id: int) -> TableTab:
    tab = db.scalar(select(TableTab).where(TableTab.table_id == table_id, TableTab.status == "open"))
    if tab is None:
        tab = TableTab(table_id=table_id, status="open", opened_at=now())
        db.add(tab)
        db.flush()
    return tab


def tab_label(db: Session, tab: TableTab) -> str | None:
    table = db.get(DiningTable, tab.table_id)
    return f"Mesa {table.label}"[:20] if table else None


def close_tab(db: Session, tab: TableTab, sale: Sale) -> None:
    """Charging the tab (inside the sale's transaction): closes it and links its orders to the sale."""
    tab.status = "closed"
    tab.closed_at = now()
    tab.sale_id = sale.id
    for o in db.scalars(select(Order).where(Order.tab_id == tab.id, Order.status != "cancelled")):
        o.sale_id = sale.id


def tab_lines(orders: list[Order]) -> list[dict[str, Any]]:
    """Billable lines of a tab: confirmed, not cancelled orders (equal lines merged)."""
    merged: dict[tuple, dict[str, Any]] = {}
    for o in orders:
        if o.status in ("pending", "cancelled"):
            continue
        for i in o.items:
            mod_ids = sorted(m["id"] for m in (i.modifiers or []) if "id" in m)
            key = (i.product_id, i.size_id, tuple(mod_ids), (i.notes or "").strip().lower())
            if key in merged:
                merged[key]["qty"] += i.qty
                continue
            merged[key] = {
                "product_id": i.product_id,
                "name": i.name_snapshot,
                "size_id": i.size_id,
                "size_name": i.size_name,
                "qty": i.qty,
                "modifier_ids": mod_ids,
                "modifiers": [m.get("name", "") for m in (i.modifiers or [])],
                "notes": i.notes,
                "unit_price_cents": i.unit_price_cents,
            }
    return list(merged.values())


def list_open_tabs(db: Session) -> list[dict[str, Any]]:
    tabs = list(db.scalars(select(TableTab).where(TableTab.status == "open").order_by(TableTab.opened_at)))
    if not tabs:
        return []
    tables = {t.id: t for t in db.scalars(select(DiningTable).where(DiningTable.id.in_({t.table_id for t in tabs})))}
    by_tab: dict[int, list[Order]] = defaultdict(list)
    for o in db.scalars(select(Order).options(selectinload(Order.items)).where(Order.tab_id.in_([t.id for t in tabs]))):
        by_tab[o.tab_id].append(o)
    out = []
    for tab in tabs:
        lines = tab_lines(by_tab[tab.id])
        if not lines:
            continue
        table = tables.get(tab.table_id)
        orders = by_tab[tab.id]
        out.append(
            {
                "id": tab.id,
                "table_id": tab.table_id,
                "table_label": table.label if table else "?",
                "opened_at": tab.opened_at,
                "orders": sum(1 for o in orders if o.status not in ("pending", "cancelled")),
                "unfinished": sum(1 for o in orders if o.status in IN_PROGRESS),
                "lines": lines,
                "total_cents": int(round(sum(ln["unit_price_cents"] * ln["qty"] for ln in lines))),
            }
        )
    return out


# ---------------------------------------------------------------- metrics


def _finished(db: Session, a: datetime, b: datetime) -> list[Order]:
    return list(
        db.scalars(
            select(Order).options(selectinload(Order.items))
            .where(Order.received_at >= a, Order.received_at < b, Order.ready_at.is_not(None), Order.status != "cancelled")
        )
    )


def _agg(rows: list[tuple[int, bool]]) -> dict[str, Any]:
    n = len(rows)
    late = sum(1 for _, is_late in rows if is_late)
    return {
        "orders": n,
        "avg_prep_s": int(round(sum(s for s, _ in rows) / n)) if n else None,
        "late": late,
        "late_pct": round(late * 100 / n, 1) if n else None,
    }


def _prep(o: Order) -> tuple[int, bool]:
    secs = max(int((o.ready_at - o.received_at).total_seconds()), 0)  # type: ignore[operator]
    return secs, secs > o.target_minutes * 60


def metrics(db: Session, start: date, end: date) -> dict[str, Any]:
    """Prep time and lateness of the orders that entered the queue in [start, end] (local days)
    and were finished (ready). Grouped by local hour, channel, product and who prepared them."""
    a, b = range_bounds_utc(start, end)
    rows = _finished(db, a, b)
    names = dict(db.execute(select(User.id, User.name)).all())
    by_hour: dict[int, list] = defaultdict(list)
    by_channel: dict[str, list] = defaultdict(list)
    by_user: dict[int | None, list] = defaultdict(list)
    by_product: dict[Any, list] = defaultdict(list)
    product_names: dict[Any, str] = {}
    product_qty: dict[Any, float] = defaultdict(float)
    for o in rows:
        r = _prep(o)
        by_hour[to_local(o.received_at).hour].append(r)  # type: ignore[arg-type]
        by_channel[o.channel].append(r)
        by_user[o.prepared_by].append(r)
        seen = set()
        for i in o.items:
            key = i.product_id or f"n:{i.name_snapshot}"
            product_names.setdefault(key, i.name_snapshot)
            product_qty[key] += i.qty
            if key not in seen:
                by_product[key].append(r)
                seen.add(key)
    total = _agg([_prep(o) for o in rows])

    def rows_of(groups: dict, label) -> list[dict[str, Any]]:
        return [{"key": str(k) if k is not None else "", "label": label(k), **_agg(v)} for k, v in groups.items()]

    products = rows_of(by_product, lambda k: product_names[k])
    for p in products:
        key = int(p["key"]) if p["key"].isdigit() else p["key"]
        p["qty"] = round(product_qty[key], 2)
    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "totals": total,
        "by_hour": sorted(rows_of(by_hour, lambda h: f"{h:02d}:00"), key=lambda r: int(r["key"])),
        "by_channel": sorted(rows_of(by_channel, lambda c: CHANNEL_LABEL.get(c, c)), key=lambda r: -r["orders"]),
        "by_product": sorted(products, key=lambda r: (-(r["avg_prep_s"] or 0), r["label"])),
        "by_user": sorted(rows_of(by_user, lambda u: names.get(u, "Sin asignar") if u else "Sin asignar"), key=lambda r: -r["orders"]),
    }


def summary(db: Session, start: date, end: date) -> dict[str, Any] | None:
    """Dashboard line: finished orders, average prep, late ones (finished late + still open and late)."""
    a, b = range_bounds_utc(start, end)
    finished = [_prep(o) for o in _finished(db, a, b)]
    t = now()
    c = cfg(db)
    open_rows = list(
        db.scalars(
            select(Order).where(
                Order.status.in_(IN_PROGRESS), Order.received_at >= max(a, t - timedelta(hours=BOARD_HOURS)), Order.received_at < b
            )
        )
    )
    open_late = sum(1 for o in open_rows if timing(o, t, c["warn_pct"])["late"])
    if not finished and not open_rows:
        return None
    agg = _agg(finished)
    return {**agg, "late": agg["late"] + open_late, "open": len(open_rows), "open_late": open_late}


def today_summary(db: Session) -> dict[str, Any] | None:
    d = local_today()
    return summary(db, d, d)
