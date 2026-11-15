"""The bell's popup: `GET /api/notifications/urgent` lists customer orders waiting for confirmation and tables
calling the waiter / asking for the bill, for any logged-in user, without customer data."""

from datetime import timedelta

from app.models import DiningTable, Order, WaiterCall
from app.services import orders as svc
from tests.conftest import login


def _order(db, number: int, source: str, status: str, table: DiningTable | None = None, age_min: int = 0) -> Order:
    o = Order(
        number=number, source=source, status=status, channel="salon" if source == "table" else "delivery",
        table_id=table.id if table else None, table_label=f"{table.label}" if table else None,
        target_minutes=8, created_at=svc.now() - timedelta(minutes=age_min),
        customer_name="Ana Pérez", customer_phone="1155550000",
    )
    db.add(o)
    db.commit()
    return o


def test_requires_a_session(seeded):
    client, _ = seeded
    assert client.get("/api/notifications/urgent").status_code == 401


def test_empty_when_nothing_is_waiting(seeded):
    client, admin = seeded
    r = client.get("/api/notifications/urgent", headers=admin)
    assert r.status_code == 200 and r.json() == {"items": [], "total": 0}


def test_lists_pending_orders_and_calls_oldest_first_without_customer_data(seeded, db):
    client, admin = seeded
    table = DiningTable(label="4", token="tok-4")
    db.add(table)
    db.commit()
    _order(db, 7, "online", "pending", age_min=5)
    _order(db, 8, "table", "pending", table, age_min=3)
    _order(db, 9, "online", "preparing", age_min=9)  # already accepted: not urgent
    t = svc.now()
    db.add(WaiterCall(table_id=table.id, kind="bill", created_at=t - timedelta(minutes=1), expires_at=t + timedelta(minutes=10)))
    db.add(WaiterCall(table_id=table.id, kind="waiter", created_at=t - timedelta(minutes=2), expires_at=t - timedelta(seconds=1)))  # expired
    db.commit()

    body = client.get("/api/notifications/urgent", headers=admin).json()
    assert body["total"] == 3
    assert [i["kind"] for i in body["items"]] == ["online_order", "table_order", "call_bill"]
    assert body["items"][0]["title"] == "Pedido online nuevo #7"
    assert "Mesa 4" in body["items"][2]["title"] and "cuenta" in body["items"][2]["title"]
    assert all(i["to"] == "/pedidos" for i in body["items"])
    text = str(body)
    assert "Ana" not in text and "1155550000" not in text  # no customer data


def test_resolved_calls_and_old_orders_drop_out(seeded, db):
    client, admin = seeded
    table = DiningTable(label="2", token="tok-2")
    db.add(table)
    db.commit()
    t = svc.now()
    db.add(WaiterCall(table_id=table.id, kind="waiter", created_at=t, expires_at=t + timedelta(minutes=10), resolved_at=t))
    _order(db, 1, "online", "pending", age_min=svc.BOARD_HOURS * 60 + 30)  # forgotten for too long
    db.commit()
    assert client.get("/api/notifications/urgent", headers=admin).json()["total"] == 0


def test_any_logged_in_role_can_read_it(seeded):
    client, admin = seeded
    r = client.post("/api/users", json={"name": "Caja Uno", "pin": "1111", "role": "cajero"}, headers=admin)
    assert r.status_code in (200, 201), r.text
    cashier = login(client, "Caja Uno", "1111")
    assert client.get("/api/notifications/urgent", headers=cashier).status_code == 200
