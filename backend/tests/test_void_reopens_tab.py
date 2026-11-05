"""Voiding a sale that charged a table's tab reopens the table's bill (same transaction as the void):
the same tab when the table has no other open one, or merged into the open one when it has."""

from sqlalchemy import func, select

from app.models import AuditLog, DiningTable, Order, StockItem, TableTab
from tests.conftest import login
from tests.test_orders import _status, _table_order, clock  # noqa: F401  (fixture)


def _charge(client, h, tab):
    items = [{"product_id": ln["product_id"], "size_id": ln["size_id"], "qty": ln["qty"], "modifier_ids": ln["modifier_ids"],
              "to_bar": False} for ln in tab["lines"]]
    r = client.post("/api/sales", headers=h, json={"items": items, "tab_id": tab["id"],
                                                  "payments": [{"method": "efectivo", "amount_cents": tab["total_cents"]}]})
    assert r.status_code == 200, r.text
    return r.json()


def _table_with_tab(client, h, db, label="9"):
    table = DiningTable(label=label, token=f"tok-{label}")
    db.add(table)
    db.commit()
    o1 = _table_order(db, table, [("Espresso", None, 2)])
    o2 = _table_order(db, table, [("Latte", None, 1)])
    for o in (o1, o2):
        assert _status(client, h, o.id, "received").status_code == 200
    for st in ("ready", "delivered"):
        _status(client, h, o1.id, st)
    return table, (o1, o2), client.get("/api/tabs", headers=h).json()[0]


def _coffee(db):
    db.expire_all()
    return db.scalar(select(StockItem.current_qty).where(StockItem.name == "Café blend de la casa"))


def test_void_reopens_the_same_tab_with_its_lines(seeded, db, clock):  # noqa: F811
    client, admin = seeded
    enc = login(client, "Encargado Demo", "3333")
    table, (o1, o2), tab = _table_with_tab(client, admin, db)
    lines = sorted((ln["name"], ln["qty"]) for ln in tab["lines"])
    coffee = _coffee(db)
    sale = _charge(client, admin, tab)
    assert client.get("/api/tabs", headers=admin).json() == []
    detail = client.get(f"/api/sales/{sale['id']}", headers=admin).json()
    assert detail["table_tab"] == {"id": tab["id"], "table_label": "Mesa 9"}
    orders_before = db.scalar(select(func.count(Order.id)))

    r = client.post(f"/api/sales/{sale['id']}/void", headers=enc, json={"reason": "Cobrado a la mesa equivocada"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "voided" and r.json()["table_tab"] is None
    assert _coffee(db) == coffee  # stock restored as with any void
    tabs = client.get("/api/tabs", headers=admin).json()
    assert [t["id"] for t in tabs] == [tab["id"]]
    assert sorted((ln["name"], ln["qty"]) for ln in tabs[0]["lines"]) == lines
    db.expire_all()
    t = db.get(TableTab, tab["id"])
    assert t.status == "open" and t.sale_id is None and t.closed_at is None
    # Orders keep their status (already made/delivered) and lose the link to the voided sale.
    assert db.get(Order, o1.id).status == "delivered" and db.get(Order, o2.id).status == "received"
    assert {db.get(Order, o.id).sale_id for o in (o1, o2)} == {None}
    assert db.scalar(select(func.count(Order.id))) == orders_before  # nothing new for the bar
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "reopen", AuditLog.entity == "table_tab"))
    assert audit.entity_id == tab["id"] and audit.payload["sale_number"] == sale["number"] and not audit.payload["merged"]

    # Charging it again works, still without sending anything to the bar.
    again = _charge(client, admin, tabs[0])
    assert again["total_cents"] == sale["total_cents"]
    assert db.scalar(select(func.count(Order.id))) == orders_before
    db.expire_all()
    assert db.get(TableTab, tab["id"]).sale_id == again["id"]


def test_void_merges_into_the_tables_new_open_tab(seeded, db, clock):  # noqa: F811
    client, admin = seeded
    table, (o1, o2), tab = _table_with_tab(client, admin, db, "3")
    sale = _charge(client, admin, tab)
    # The table keeps ordering after being charged: a new open tab.
    o3 = _table_order(db, table, [("Espresso", None, 1)])
    _status(client, admin, o3.id, "received")
    new_tab = client.get("/api/tabs", headers=admin).json()[0]
    assert new_tab["id"] != tab["id"]

    assert client.post(f"/api/sales/{sale['id']}/void", headers=admin, json={"reason": "Error"}).status_code == 200
    tabs = client.get("/api/tabs", headers=admin).json()
    assert [t["id"] for t in tabs] == [new_tab["id"]]  # one bill per table
    assert {ln["name"]: ln["qty"] for ln in tabs[0]["lines"]} == {"Espresso": 3, "Latte": 1}
    db.expire_all()
    assert db.get(TableTab, tab["id"]).status == "merged"
    assert {db.get(Order, o.id).tab_id for o in (o1, o2, o3)} == {new_tab["id"]}
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "reopen"))
    assert audit.entity_id == new_tab["id"] and audit.payload["merged"] and audit.payload["voided_tab_id"] == tab["id"]


def test_void_of_an_ordinary_sale_touches_no_tab(seeded, db, clock):  # noqa: F811
    client, admin = seeded
    table, _orders, tab = _table_with_tab(client, admin, db, "5")
    pid = tab["lines"][0]["product_id"]
    r = client.post("/api/sales", headers=admin, json={"items": [{"product_id": pid}],
                                                      "payments": [{"method": "efectivo", "amount_cents": 220000}]})
    assert r.status_code == 200, r.text
    assert r.json()["table_tab"] is None
    client.post(f"/api/sales/{r.json()['id']}/void", headers=admin, json={"reason": "Error"})
    assert [t["id"] for t in client.get("/api/tabs", headers=admin).json()] == [tab["id"]]
    assert db.scalar(select(AuditLog).where(AuditLog.action == "reopen")) is None


def test_void_is_atomic_with_the_reopen(seeded, db, clock, monkeypatch):  # noqa: F811
    client, admin = seeded
    _table, _orders, tab = _table_with_tab(client, admin, db, "6")
    sale = _charge(client, admin, tab)
    from app.services import sales as sales_svc

    def boom(*_a, **_k):
        raise RuntimeError("fallo al final")

    monkeypatch.setattr(sales_svc.audit, "log", boom)
    try:
        client.post(f"/api/sales/{sale['id']}/void", headers=admin, json={"reason": "Error"})
    except RuntimeError:
        pass
    db.expire_all()
    assert db.get(TableTab, tab["id"]).status == "closed"
    assert client.get(f"/api/sales/{sale['id']}", headers=admin).json()["status"] == "completed"
