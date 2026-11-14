"""Order queue for the bar/kitchen screen: lifecycle, timers/late flags, open tabs per table and metrics.

Lifecycle: one order model with one path per origin (POS sale, table QR, online take away/delivery),
see FLOWS below. POS sales become `received` orders automatically (per channel and per category, see the
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
from sqlalchemy import Integer, case, cast, func, select
from sqlalchemy.orm import Session, selectinload

from app.db import lock_writes
from app.licensing import has_feature
from app.models import (
    CollectCharge,
    Customer,
    DiningTable,
    Order,
    OrderItem,
    OrderStation,
    Product,
    ProductCategory,
    Sale,
    TableDiner,
    TableTab,
    User,
    WaiterCall,
    utcnow,
)
from app.models.sales import CHANNELS
from app.services import audit, business_profile, order_flows, printing, settings
from app.services.timeutil import day_bounds_utc, local_today, range_bounds_utc, to_local

# Every order follows the flow (strategy) of its channel: services/order_flows.py.
# Statuses shown on the order screen; IN_PROGRESS = in the bar queue with the clock running.
ACTIVE = ("pending", "received", "accepted", "awaiting_pay", "paid", "preparing", "ready", "dispatched")
IN_PROGRESS = ("received", "accepted", "paid", "preparing")
STATUS_LABEL = {
    "pending": "Por confirmar",
    "received": "Confirmado",
    "accepted": "Aceptado",
    "awaiting_pay": "Pago pendiente",
    "paid": "Pagado",
    "preparing": "En preparación",
    "ready": "Listo",
    "dispatched": "Enviado",
    "delivered": "Entregado",
    "cancelled": "Cancelado",
    "rejected": "Rechazado",
    "expired": "Vencido",
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
    printing.queue_comandas(db, out)  # direct-printed kitchen tickets, sent after the commit
    return out


def next_number(db: Session) -> int:
    lock_writes(db)  # same race as sale numbers (and orders have no unique constraint: duplicates were silent)
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
    if not business_profile.is_enabled(db, "orders"):  # hidden for this business type: no stale orders
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


def status_label(o: Order) -> str:
    """The step's name in this order's own flow ("Servido" at a table, "Retirado" for take away…)."""
    if o.status == "cancelled" and o.payment_status == "refunded":
        return "Cancelado · devuelto"
    flow = order_flows.flow_of(o)
    try:
        return flow.state(o.status).label
    except StopIteration:
        return STATUS_LABEL.get(o.status, o.status)


def queue_status(o: Order) -> str:
    """Where a confirmed order waits for the bar ("Nuevos")."""
    if o.source != "online":
        return "received"
    return "accepted" if o.payment_method == "cash" else "paid"


def actions(o: Order, db: Session | None = None) -> list[dict[str, Any]]:
    """Buttons for the order's current state (the screen renders them from data), filtered by guards."""
    flow = order_flows.flow_of(o)
    try:
        state = flow.state(o.status)
    except StopIteration:
        return []
    paid = o.payment_status == "paid"
    out = []
    for a in state.actions:
        # "preview": guards that depend on what the user types (a reason) don't hide the button.
        ctx = order_flows.Ctx(db=db, actor=None, frm=o.status, to=a.to, via="preview")  # type: ignore[arg-type]
        if flow.check(o, ctx) is None:
            out.append(order_flows.action_out(a, paid))
    return out


def set_status(db: Session, order_id: int, status: str, user: User, reason: str | None = None,
               params: dict[str, Any] | None = None) -> Order:
    """The screen's buttons: one action of the order's current state."""
    o = get_order(db, order_id)
    transition(db, o, status, user, reason, params)
    db.commit()
    return o


def transition(db: Session, o: Order, to: str, actor: User | None, reason: str | None = None,
               params: dict[str, Any] | None = None, via: str = "ui") -> Order:
    """The single way an order changes state (no commit: the caller's transaction).

    Validates the move against the order's flow (`via="ui"`: only the current state's actions;
    `via="system"`: any declared transition, e.g. payment approval, expiry, a tab charge), runs the
    flow's guards and effects, audits and raises a clear 409 for invalid moves."""
    flow = order_flows.flow_of(o)
    frm = o.status
    ctx = order_flows.Ctx(db=db, actor=actor, frm=frm, to=to, reason=reason, params=params or {}, via=via)

    def refuse(msg: str | None = None) -> HTTPException:
        return HTTPException(
            409, msg or f"El pedido #{o.number} está «{status_label(o)}»: no se puede pasar a «{_target_label(flow, to)}»"
        )

    if not flow.allows(frm, to):
        raise refuse()
    if via == "ui" and to not in {a.to for a in flow.state(frm).actions}:
        raise refuse()
    msg = flow.check(o, ctx)
    if msg:
        raise refuse(msg)
    o.status = to
    flow.run_effects(o, ctx)
    if o.status == to and to == queue_status(o) and o.received_at is None:
        _enter_queue(db, o, actor)
    if o.source == "online":
        o.sync_pending = True  # the customer's tracking page learns it on the next sync
    uid = actor.id if actor else None
    if to in ("cancelled", "rejected", "accepted") or (frm == "pending" and to == "received"):
        action = {"cancelled": "cancel", "rejected": "reject", "accepted": "accept", "received": "confirm"}[to]
        audit.log(db, uid, action, "order", o.id,
                  {"number": o.number, "flow": flow.key, "from": frm, "reason": o.cancel_reason, "table": o.table_label})
    elif via == "system" or o.source == "online":
        audit.log(db, uid, "status", "order", o.id, {"number": o.number, "flow": flow.key, "from": frm, "to": to, "via": via})
    return o


def _target_label(flow: order_flows.OrderFlow, to: str) -> str:
    try:
        return flow.state(to).label
    except StopIteration:
        return STATUS_LABEL.get(to, to)


def _enter_queue(db: Session, o: Order, actor: User | None) -> None:
    """A confirmed/accepted/paid order enters the bar queue: its clock starts and it's routed to stations."""
    o.received_at = now()
    if actor is not None and o.confirmed_by is None:
        o.confirmed_by = actor.id
    route_stations(db, o)


# ---------------------------------------------------------------- core effects (timestamps, tabs)


def _fx_confirm_table(o: Order, c: order_flows.Ctx) -> None:
    if o.table_id is not None:
        o.tab_id = open_tab(c.db, o.table_id).id
    if o.diner_id is not None and c.actor is not None:  # a waiter vouched for this phone (table session trust)
        diner = c.db.get(TableDiner, o.diner_id)
        if diner is not None:
            diner.trusted = True


def _fx_back_to_queue(o: Order, c: order_flows.Ctx) -> None:
    o.started_at = None


def _fx_start(o: Order, c: order_flows.Ctx) -> None:
    if c.frm == "ready":
        o.ready_at = None
    o.started_at = o.started_at or now()
    o.prepared_by = o.prepared_by or (c.actor.id if c.actor else None)


def _fx_ready(o: Order, c: order_flows.Ctx) -> None:
    if c.frm in ("delivered", "dispatched"):
        o.delivered_at = None
        o.dispatched_at = None
        if c.frm == "delivered" and o.source == "online" and o.payment_method == "cash":
            o.payment_status = "unpaid"
    else:
        o.ready_at = now()
        o.prepared_by = o.prepared_by or (c.actor.id if c.actor else None)


def _fx_dispatched(o: Order, c: order_flows.Ctx) -> None:
    if c.frm == "delivered":
        o.delivered_at = None
        if o.payment_method == "cash":
            o.payment_status = "unpaid"
    else:
        o.dispatched_at = now()


def _fx_delivered(o: Order, c: order_flows.Ctx) -> None:
    o.delivered_at = now()
    if o.source == "online" and o.payment_method == "cash":
        o.payment_status = "paid"  # collected on delivery / at pickup
        o.paid_at = o.paid_at or now()
    if o.source == "table" and o.payment_status == "paid":
        transition(c.db, o, "paid", c.actor, via="system")  # the tab was charged before it was served


def _fx_table_paid(o: Order, c: order_flows.Ctx) -> None:
    o.payment_status = "paid"


def _fx_table_reopened(o: Order, c: order_flows.Ctx) -> None:
    o.payment_status = "unpaid"


def _fx_accepted(o: Order, c: order_flows.Ctx) -> None:
    o.accepted_at = now()
    o.confirmed_by = c.actor.id if c.actor else o.confirmed_by
    eta = c.params.get("eta_minutes")
    if eta is not None:
        o.eta_minutes = max(1, min(int(eta), 600))


def _fx_paid(o: Order, c: order_flows.Ctx) -> None:
    o.payment_status = "paid"
    o.paid_at = o.paid_at or now()
    o.expires_at = None


def _fx_closed(o: Order, c: order_flows.Ctx) -> None:
    o.cancelled_at = now()
    o.cancel_reason = (c.reason or "").strip()[:200] or None
    o.expires_at = None


def _fx_reason_required(o: Order, c: order_flows.Ctx) -> str | None:
    if (c.reason or "").strip() or c.via in ("system", "preview"):
        return None
    return "Contale al cliente el motivo del rechazo."


def _g_cash_only(o: Order, c: order_flows.Ctx) -> str | None:
    return None if o.payment_method == "cash" else "El pedido todavía no está pagado."


def _g_back_to_own_queue(o: Order, c: order_flows.Ctx) -> str | None:
    return None if c.to == queue_status(o) else "Ese no es el paso anterior de este pedido."


def _g_manual_payment(o: Order, c: order_flows.Ctx) -> str | None:
    if c.via == "system" or o.payment_method == "transfer":
        return None
    return "El pago online se acredita solo cuando se aprueba."


def _register_core_effects() -> None:
    F = order_flows
    every = tuple(F.FLOWS)
    online = ("take_away", "delivery")
    F.on("mesa", "pending", "received", _fx_confirm_table)
    for back in ("received", "accepted", "paid"):
        F.on(every, "preparing", back, _fx_back_to_queue)
    F.on(every, "*", "preparing", _fx_start)
    F.on(every, "*", "ready", _fx_ready)
    F.on("delivery", "*", "dispatched", _fx_dispatched)
    F.on(("caja", "take_away", "delivery"), "*", "delivered", _fx_delivered)
    F.on("mesa", "ready", "delivered", _fx_delivered)
    F.on("mesa", "delivered", "paid", _fx_table_paid)
    F.on("mesa", "paid", "delivered", _fx_table_reopened)
    F.on(online, "pending", "accepted", _fx_accepted)
    F.on(online, "*", "paid", _fx_paid)
    for exit_ in ("cancelled", "rejected", "expired"):
        F.on(every if exit_ == "cancelled" else online, "*", exit_, _fx_closed)
    F.guard(online, "pending", "rejected", _fx_reason_required)
    F.guard(online, "accepted", "preparing", _g_cash_only)
    F.guard(online, "accepted", "ready", _g_cash_only)
    F.guard(online, "preparing", "accepted", _g_back_to_own_queue)
    F.guard(online, "preparing", "paid", _g_back_to_own_queue)
    F.guard(online, "awaiting_pay", "paid", _g_manual_payment)


_register_core_effects()


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


def serialize(o: Order, t: datetime, warn_pct: int, names: dict[int, str], sale_numbers: dict[int, int],
              customers: dict[int, Customer] | None = None) -> dict[str, Any]:
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
        "flow": order_flows.flow_key(o),
        "status_label": status_label(o),
        "column": _column(o),
        "actions": actions(o),
        "payment_status": o.payment_status,
        "online": online_info(o, t, (customers or {}).get(o.customer_id or 0)) if o.source == "online" else None,
        **timing(o, t, warn_pct),
    }


def _column(o: Order) -> str:
    try:
        return order_flows.flow_of(o).state(o.status).column
    except StopIteration:
        return "done"


def customer_changes(o: Order, c: Customer | None) -> list[dict[str, Any]]:
    """What an online order brought that differs from the saved customer («Datos nuevos»). An anonymous
    order never changes the customer by itself: staff applies it with «Actualizar datos del cliente»."""
    if c is None:
        return []
    pairs = [("name", "Nombre", c.name, o.customer_name)]
    if o.channel == "delivery":
        pairs += [("address", "Dirección", c.address, o.address), ("address_ref", "Referencia", c.address_ref, o.address_ref)]
    return [{"field": f, "label": lbl, "saved": old, "new": new}
            for f, lbl, old, new in pairs if new and (old or "").strip() != new.strip()]


def _json_or_none(text: str | None) -> dict[str, Any] | None:
    import json

    try:
        data = json.loads(text) if text else None
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def online_info(o: Order, t: datetime, customer: Customer | None = None) -> dict[str, Any]:
    """What the order screen shows (and acts on) for a take away / delivery order from the online menu."""
    return {
        "customer_id": o.customer_id,
        "customer_name": o.customer_name,
        "customer_phone": o.customer_phone,
        "address": o.address,
        "address_ref": o.address_ref,
        "delivery_zone": o.delivery_zone,
        "delivery_fee_cents": o.delivery_fee_cents,
        "total_cents": o.total_cents,
        "payment_method": o.payment_method,
        "payment_url": o.payment_url,
        "charge_id": int(o.payment_ref) if o.payment_method == "online" and (o.payment_ref or "").isdigit() else None,
        "refunded_cents": o.refunded_cents,
        "eta_minutes": o.eta_minutes,
        "accepted_at": o.accepted_at,
        "paid_at": o.paid_at,
        "expires_at": o.expires_at,
        "expires_in_s": (
            max(int((o.expires_at - t).total_seconds()), 0) if o.expires_at and o.status == "awaiting_pay" else None
        ),
        "tracking_url": o.tracking_url,
        "cancel_reason": o.cancel_reason,
        "sale_registered": o.sale_id is not None,
        "invoice_request": _json_or_none(o.invoice_request),
        "customer_changes": customer_changes(o, customer),
    }


def _sort_key(row: dict[str, Any]) -> tuple:
    rank = {"pending": 0, "awaiting_pay": 0, "ready": 2, "dispatched": 2}.get(row["status"], 1)
    if row["status"] in IN_PROGRESS and row["received_at"] is not None:  # late first (most overdue on top), then oldest first
        overdue = row["elapsed_s"] - row["target_minutes"] * 60
        return (rank, 0 if row["late"] else 1, -overdue if row["late"] else 0, row["received_at"])
    return (rank, 0, 0, row["ready_at"] or row["received_at"] or row["created_at"])


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
    cids = {o.customer_id for o in rows if o.customer_id and o.source == "online"}
    customers = {cu.id: cu for cu in db.scalars(select(Customer).where(Customer.id.in_(cids)))} if cids else {}
    orders = sorted((serialize(o, t, c["warn_pct"], names, sale_numbers, customers) for o in rows), key=_sort_key)
    stations = active_stations(db)
    direct = printing.station_printers(db) if stations else {}
    return {
        "server_time": t,
        "settings": c,
        "pro": pro(),
        "stations": [
            {"id": st.id, "name": st.name, "print_tickets": st.print_tickets, "direct_print": st.id in direct}
            for st in stations
        ],
        # Kitchen tickets the thermal printer couldn't print: the station's screen prints them instead.
        "print_failures": printing.failures(station_id) if direct else [],
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
            Order.created_at >= t - timedelta(hours=BOARD_HOURS),
            Order.status.not_in(("cancelled", "rejected", "expired", "pending", "awaiting_pay", "dispatched")),
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


def effective_waiter(db: Session, table_id: int | None, tab_id: int | None = None) -> int | None:
    """Employee serving a table: the open tab's waiter, else the table's own, else its zone's (None if nobody).
    The first assignment found wins; if that employee is no longer active the result is None (the sale never
    gets a waiter who left, and it doesn't fall through to the zone's)."""
    from app.models import Employee, FloorZone

    tab = db.get(TableTab, tab_id) if tab_id is not None else None
    if table_id is None and tab is not None:
        table_id = tab.table_id
    table = db.get(DiningTable, table_id) if table_id is not None else None
    candidates = [
        tab.waiter_employee_id if tab else None,
        table.waiter_employee_id if table else None,
    ]
    if table is not None and table.zone_id is not None:
        zone = db.get(FloorZone, table.zone_id)
        candidates.append(zone.waiter_employee_id if zone else None)
    for emp_id in candidates:
        if emp_id is None:
            continue
        emp = db.get(Employee, emp_id)
        return emp.id if emp is not None and emp.active else None
    return None


def open_tab(db: Session, table_id: int) -> TableTab:
    tab = db.scalar(select(TableTab).where(TableTab.table_id == table_id, TableTab.status == "open"))
    if tab is None:
        tab = TableTab(table_id=table_id, status="open", opened_at=now())
        db.add(tab)
        db.flush()
        tab.waiter_employee_id = effective_waiter(db, table_id)  # the account starts with the table's waiter
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
        if o.status == "delivered":  # servido → pagado
            transition(db, o, "paid", None, via="system")
        else:  # still in the bar: becomes pagado once served
            o.payment_status = "paid"


def tab_of_sale(db: Session, sale_id: int) -> TableTab | None:
    """The table tab a sale charged (None for ordinary sales)."""
    return db.scalar(select(TableTab).where(TableTab.sale_id == sale_id, TableTab.status == "closed"))


def reopen_tab(db: Session, sale: Sale, user: User) -> dict[str, Any] | None:
    """Voiding a sale that charged a table's tab gives the table its bill back (inside the void's
    transaction). If the table has no other open tab, the same tab is reopened. If it already has one
    (people sat down again and ordered after the voided charge), the voided tab's orders are moved
    into that open tab, so the table keeps a single bill, and the voided tab is marked `merged`.
    The orders keep their status (they were already made and delivered): only their link to the
    voided sale is removed, and charging the tab again sends its lines with `to_bar=false`, so
    nothing reaches the bar twice."""
    tab = tab_of_sale(db, sale.id)
    if tab is None:
        return None
    other = db.scalar(
        select(TableTab).where(TableTab.table_id == tab.table_id, TableTab.status == "open", TableTab.id != tab.id)
    )
    target = other or tab
    for o in db.scalars(select(Order).where(Order.tab_id == tab.id)):
        if o.sale_id == sale.id:
            o.sale_id = None
        if o.status == "paid":
            transition(db, o, "delivered", user, via="system")
        o.payment_status = "unpaid"
        o.tab_id = target.id
    if other is None:
        tab.status = "open"
        tab.closed_at = None
        tab.sale_id = None
    else:
        tab.status = "merged"
    label = tab_label(db, tab)
    audit.log(
        db, user.id, "reopen", "table_tab", target.id,
        {"sale_number": sale.number, "table": label, "voided_tab_id": tab.id, "merged": other is not None},
    )
    return {"tab_id": target.id, "table_label": label, "merged": other is not None}


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
    prepaid: dict[int, tuple[int, int]] = {}
    for ch in db.scalars(select(CollectCharge).where(
            CollectCharge.ref_type == "table_tab", CollectCharge.ref_id.in_([t.id for t in tabs]),
            CollectCharge.sale_id.is_(None), CollectCharge.status.in_(("pending", "approved")))):
        a, p = prepaid.get(ch.ref_id, (0, 0))  # type: ignore[arg-type]
        bill = ch.amount_cents - (ch.tip_cents or 0)  # a tip is not part of the bill the cashier still has to collect
        prepaid[ch.ref_id] = (a + bill, p) if ch.status == "approved" else (a, p + bill)  # type: ignore[index]
    bill_tables = {c["table_id"] for c in active_calls(db) if c["kind"] == "bill"}
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
                "prepaid_cents": prepaid.get(tab.id, (0, 0))[0],  # paid from the phones, not charged yet
                "paying_cents": prepaid.get(tab.id, (0, 0))[1],  # a payment from a phone is in progress
                "bill_requested": tab.table_id in bill_tables,  # the table (or its waiter) asked for the bill
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


def _agg_totals(n: int, total_secs: int, late: int) -> dict[str, Any]:
    return {
        "orders": n,
        "avg_prep_s": int(round(total_secs / n)) if n else None,
        "late": late,
        "late_pct": round(late * 100 / n, 1) if n else None,
    }


def _agg(rows: list[tuple[int, bool]]) -> dict[str, Any]:
    return _agg_totals(len(rows), sum(s for s, _ in rows), sum(1 for _, is_late in rows if is_late))


def _secs_between(start, end):
    """Whole seconds from `start` to `end` (SQLite DATETIME text), never negative: the SQL twin of `_prep`'s
    `max(int((ready - received).total_seconds()), 0)`. `julianday` is a float, so half a millisecond is added
    before truncating to absorb its rounding error (sub-millisecond differences are irrelevant here)."""
    whole = cast((func.julianday(end) - func.julianday(start)) * 86400.0 + 0.0005, Integer)
    return case((whole > 0, whole), else_=0)


def _finished_stats(db: Session, a: datetime, b: datetime) -> dict[str, Any]:
    """Same numbers as `_agg(_prep(o) for o in _finished(...))` in one aggregate query (no ORM objects, no items)."""
    inner = (
        select(_secs_between(Order.received_at, Order.ready_at).label("secs"), (Order.target_minutes * 60).label("limit"))
        .where(Order.received_at >= a, Order.received_at < b, Order.ready_at.is_not(None), Order.status != "cancelled")
        .subquery()  # the seconds are computed once per row, not once per aggregate
    )
    n, total, late = db.execute(
        select(func.count(), func.coalesce(func.sum(inner.c.secs), 0),
               func.coalesce(func.sum(case((inner.c.secs > inner.c.limit, 1), else_=0)), 0))
    ).one()
    return _agg_totals(int(n), int(total), int(late))


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
    agg = _finished_stats(db, a, b)
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
    if not agg["orders"] and not open_rows:
        return None
    return {**agg, "late": agg["late"] + open_late, "open": len(open_rows), "open_late": open_late}


def today_summary(db: Session) -> dict[str, Any] | None:
    d = local_today()
    return summary(db, d, d)
