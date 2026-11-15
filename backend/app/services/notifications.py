"""What needs attention RIGHT NOW (the bell's popup): customer orders waiting for confirmation and tables
calling the waiter or asking for the bill. Read-only; the same data the Orders board shows, in a compact list.
Alerts (stock, expiries, expenses…) come from the alerts service; this only adds the live, order-related part."""

from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order
from app.services import orders as orders_svc

MAX_ITEMS = 20


def urgent(db: Session) -> dict[str, Any]:
    """`items` (oldest first) and `total`. Each item: key, kind, title, detail, at, to (frontend route).
    Kinds: online_order | table_order | call_waiter | call_bill. No customer data: names and phones stay in Orders."""
    t = orders_svc.now()
    since = t - timedelta(hours=orders_svc.BOARD_HOURS)
    items: list[dict[str, Any]] = []

    pending = db.execute(
        select(Order.id, Order.number, Order.source, Order.table_label, Order.created_at)
        .where(Order.status == "pending", Order.created_at >= since)
        .order_by(Order.created_at)
    ).all()
    for oid, number, source, table_label, created_at in pending:
        if source == "online":
            items.append(
                {"key": f"order:{oid}", "kind": "online_order", "title": f"Pedido online nuevo #{number}", "detail": "Esperando que lo aceptes", "at": created_at, "to": "/pedidos"}
            )
        else:
            where = f"Mesa {table_label}" if table_label else "Una mesa"
            items.append(
                {"key": f"order:{oid}", "kind": "table_order", "title": f"{where}: pedido para confirmar", "detail": f"Pedido #{number}", "at": created_at, "to": "/pedidos"}
            )

    for call in orders_svc.active_calls(db, t):
        bill = call["kind"] == "bill"
        items.append(
            {
                "key": f"call:{call['id']}",
                "kind": "call_bill" if bill else "call_waiter",
                "title": f"Mesa {call['table_label']}: {'pidió la cuenta' if bill else 'llama al mozo'}",
                "detail": None,
                "at": call["created_at"],
                "to": "/pedidos",
            }
        )

    items.sort(key=lambda i: i["at"])
    return {"items": items[:MAX_ITEMS], "total": len(items)}
