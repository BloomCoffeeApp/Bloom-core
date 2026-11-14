"""Order screen (bar/kitchen): live board, status changes, waiter calls, settings and open tabs."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import CurrentUser, Perm
from app.db import get_db
from app.models import User
from app.schemas.common import Ok
from app.schemas.orders import BoardOut, OrderOut, OrdersSettings, OrderStatusIn, TabOut
from app.services import order_flows, roles
from app.services import orders as svc

router = APIRouter(prefix="/api", tags=["orders"])

Manager = Perm("orders.manage")
Seller = Perm("pos.sell")
# Moving orders along / answering waiter calls: the floor, the kitchen/bar and the register (as before).
Floor = Perm("tables.serve", "kitchen.use", "orders.manage", "pos.sell")
# Cancelling or rejecting an order: the register, the floor or the manager. The kitchen only moves orders forward.
CANCELLERS = ("orders.manage", "pos.sell", "tables.serve")


@router.get("/orders/board", response_model=BoardOut)
def board(station_id: int | None = None, db: Session = Depends(get_db), _: User = CurrentUser) -> dict:
    # Polled every ~2 s by each screen (see PLAN.md §9): small payload, no server push.
    return svc.board(db, station_id)


@router.post("/orders/{order_id}/status", response_model=OrderOut)
def set_status(order_id: int, data: OrderStatusIn, db: Session = Depends(get_db), user: User = Floor) -> dict:
    if data.status in ("cancelled", "rejected") and not roles.has(user, *CANCELLERS):
        raise HTTPException(403, "Cancelar o rechazar un pedido lo hace la caja o el encargado")
    params = {"eta_minutes": data.eta_minutes} if data.eta_minutes is not None else None
    svc.set_status(db, order_id, data.status, user, data.reason, params)
    row = next((o for o in svc.board(db)["orders"] if o["id"] == order_id), None)
    if row is not None:
        return row
    o = svc.get_order(db, order_id)
    return svc.serialize(o, svc.now(), svc.cfg(db)["warn_pct"], {}, {})


@router.get("/orders/flows")
def flows(_: User = CurrentUser) -> list[dict]:
    """Each channel's flow: states in order, allowed next states and the buttons of each state."""
    return order_flows.describe_all()


@router.post("/waiter-calls/{call_id}/resolve", response_model=Ok)
def resolve_call(call_id: int, db: Session = Depends(get_db), user: User = Floor) -> Ok:
    svc.resolve_call(db, call_id, user)
    return Ok()


@router.get("/orders/settings", response_model=OrdersSettings)
def get_settings(db: Session = Depends(get_db), _: User = CurrentUser) -> dict:
    return svc.cfg(db)


@router.put("/orders/settings", response_model=OrdersSettings)
def put_settings(data: OrdersSettings, db: Session = Depends(get_db), user: User = Manager) -> dict:
    return svc.save_cfg(db, data.model_dump(), user)


@router.get("/tabs", response_model=list[TabOut])
def open_tabs(db: Session = Depends(get_db), _: User = Seller) -> list[dict]:
    return svc.list_open_tabs(db)
