"""Order state machine: one declarative flow (strategy) per channel. Walks every flow's valid path,
checks invalid moves fail with 409, UI-vs-system transitions, guards and the API description."""

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import Order, User
from app.services import order_flows, orders


def _order(db, source="pos", channel="salon", status="received", payment_method=None, **kw) -> Order:
    t = orders.now()
    o = Order(number=orders.next_number(db), source=source, status=status, channel=channel, created_at=t,
              received_at=t if status == "received" else None, payment_method=payment_method, **kw)
    db.add(o)
    db.flush()
    return o


def _user(db) -> User:
    return db.scalar(select(User).order_by(User.id))


def _walk(db, o, path, user, system=()):
    for to in path:
        orders.transition(db, o, to, user, reason="motivo" if to in ("rejected", "cancelled") else None,
                          params={"eta_minutes": 25} if to == "accepted" else None,
                          via="system" if to in system else "ui")
        assert o.status == to


def test_flows_are_declared_consistently():
    assert set(order_flows.FLOWS) == {"caja", "mesa", "take_away", "delivery"}
    for flow in order_flows.FLOWS.values():
        keys = [s.key for s in flow.states]
        assert len(keys) == len(set(keys))
        for s in flow.states:  # every button is an allowed transition (checked at import too)
            assert all(flow.allows(s.key, a.to) for a in s.actions)
    assert not order_flows.DELIVERY.allows("ready", "delivered")  # delivery: listo → enviado → entregado
    assert not order_flows.TAKE_AWAY.allows("ready", "dispatched")  # take away: listo → retirado


def test_flow_is_chosen_by_the_order():
    assert order_flows.flow_key(Order(source="pos", channel="llevar")) == "caja"
    assert order_flows.flow_key(Order(source="table", channel="salon")) == "mesa"
    assert order_flows.flow_key(Order(source="online", channel="llevar")) == "take_away"
    assert order_flows.flow_key(Order(source="online", channel="delivery")) == "delivery"


def test_caja_path_and_invalid_moves(seeded, db):
    user = _user(db)
    o = _order(db)
    _walk(db, o, ["preparing", "ready", "delivered"], user)
    assert o.delivered_at is not None and orders.status_label(o) == "Entregado"
    for bad in ("pending", "paid", "accepted", "cancelled"):
        with pytest.raises(HTTPException) as e:
            orders.transition(db, o, bad, user)
        assert e.value.status_code == 409


def test_mesa_path_until_paid_by_the_tab(seeded, db):
    user = _user(db)
    o = _order(db, source="table", status="pending")
    _walk(db, o, ["received", "preparing", "ready", "delivered"], user)
    assert orders.status_label(o) == "Servido" and o.received_at is not None
    with pytest.raises(HTTPException):  # «pagado» only when the tab is charged (system)
        orders.transition(db, o, "paid", user)
    orders.transition(db, o, "paid", None, via="system")
    assert o.status == "paid" and o.payment_status == "paid"


@pytest.mark.parametrize("channel,ending", [("llevar", ["delivered"]), ("delivery", ["dispatched", "delivered"])])
def test_online_paid_path(seeded, db, channel, ending):
    user = _user(db)
    o = _order(db, source="online", channel=channel, status="pending", payment_method="transfer", total_cents=100000)
    orders.transition(db, o, "accepted", user, params={"eta_minutes": 25})
    assert o.eta_minutes == 25 and o.accepted_at is not None
    if o.status == "accepted":  # without Pro no effect chains the payment step
        orders.transition(db, o, "awaiting_pay", None, via="system")
    assert o.status == "awaiting_pay" and o.received_at is None  # not in the bar until it's paid
    with pytest.raises(HTTPException):  # the bar can't start an unpaid order
        orders.transition(db, o, "preparing", user)
    orders.transition(db, o, "paid", user)  # «Pago recibido» (transfer)
    assert o.payment_status == "paid" and o.received_at is not None
    _walk(db, o, ["preparing", "ready", *ending], user)
    label = "Retirado" if channel == "llevar" else "Entregado"
    assert orders.status_label(o) == label


def test_online_cash_skips_the_payment_step(seeded, db):
    user = _user(db)
    o = _order(db, source="online", channel="llevar", status="pending", payment_method="cash")
    _walk(db, o, ["accepted", "preparing", "ready", "delivered"], user)
    assert o.payment_status == "paid"  # collected at pickup


def test_online_exits_and_guards(seeded, db):
    user = _user(db)
    o = _order(db, source="online", channel="delivery", status="pending", payment_method="online")
    with pytest.raises(HTTPException) as e:  # rejecting needs a reason for the customer
        orders.transition(db, o, "rejected", user)
    assert e.value.status_code == 409
    orders.transition(db, o, "rejected", user, reason="Sin stock")
    assert o.status == "rejected" and o.cancel_reason == "Sin stock"
    with pytest.raises(HTTPException):
        orders.transition(db, o, "accepted", user)

    o2 = _order(db, source="online", channel="llevar", status="awaiting_pay", payment_method="online")
    with pytest.raises(HTTPException) as e:  # an online payment is approved by the provider, not by hand
        orders.transition(db, o2, "paid", user)
    assert "se acredita solo" in e.value.detail
    with pytest.raises(HTTPException):  # expiring is the system's job
        orders.transition(db, o2, "expired", user)
    orders.transition(db, o2, "expired", None, "No se pagó a tiempo", via="system")
    assert o2.status == "expired" and orders.status_label(o2) == "Vencido"


def test_actions_are_data_filtered_by_guards(seeded, db):
    o = _order(db, source="online", channel="llevar", status="preparing", payment_method="transfer", payment_status="paid")
    labels = [(a["to"], a["label"]) for a in orders.actions(o)]
    assert ("ready", "Listo") in labels and ("paid", "Volver a «Nuevo»") in labels
    assert ("accepted", "Volver a «Nuevo»") not in labels  # only the order's own queue
    assert ("cancelled", "Cancelar y devolver") in labels  # paid: the cancel button says it refunds
    pending = _order(db, source="online", channel="delivery", status="pending", payment_method="cash")
    assert [a["needs"] for a in orders.actions(pending)] == ["eta", "reason"]


def test_flows_endpoint_and_board_render_from_data(seeded, db):
    client, admin = seeded
    flows = client.get("/api/orders/flows", headers=admin).json()
    assert [f["key"] for f in flows] == ["caja", "mesa", "take_away", "delivery"]
    delivery = next(f for f in flows if f["key"] == "delivery")
    assert [s["key"] for s in delivery["states"]][:4] == ["pending", "accepted", "awaiting_pay", "paid"]
    pending = next(s for s in delivery["states"] if s["key"] == "pending")
    assert {a["to"] for a in pending["actions"]} == {"accepted", "rejected"}
    _order(db, source="online", channel="delivery", status="pending", payment_method="cash", customer_name="Juan")
    db.commit()
    row = client.get("/api/orders/board", headers=admin).json()["orders"][0]
    assert row["flow"] == "delivery" and row["column"] == "confirm" and row["online"]["customer_name"] == "Juan"
    assert [a["to"] for a in row["actions"]] == ["accepted", "rejected"]
    r = client.post(f"/api/orders/{row['id']}/status", headers=admin, json={"status": "accepted", "eta_minutes": 30})
    assert r.status_code == 200 and r.json()["status"] == "accepted" and r.json()["online"]["eta_minutes"] == 30
    assert client.post(f"/api/orders/{row['id']}/status", headers=admin, json={"status": "paid"}).status_code == 409
