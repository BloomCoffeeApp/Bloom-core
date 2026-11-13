"""Core side of the waiter snapshot: charging a table's tab stores the table and its effective waiter
(tab -> table -> zone), and works exactly as before when nobody is assigned (also without Pro)."""

from sqlalchemy import select

from app.models import DiningTable, Employee, FloorZone, Sale, TableTab
from app.services import orders
from tests.test_orders import _status, _table_order, clock  # noqa: F401  (fixture)
from tests.test_void_reopens_tab import _charge, _table_with_tab


def _emp(db, name, active=True):
    e = Employee(name=name, active=active)
    db.add(e)
    db.commit()
    return e


def test_sale_without_any_waiter_is_unchanged(seeded, db, clock):  # noqa: F811
    client, admin = seeded
    table, _orders, tab = _table_with_tab(client, admin, db)
    sale = _charge(client, admin, tab)
    row = db.get(Sale, sale["id"])
    assert row.waiter_employee_id is None and row.table_id == table.id
    detail = client.get(f"/api/sales/{sale['id']}", headers=admin).json()
    assert detail["waiter_name"] is None and detail["waiter_employee_id"] is None


def test_ordinary_sale_has_no_table_or_waiter(seeded, db):
    client, admin = seeded
    from sqlalchemy import select as sel

    from app.models import Product

    pid = db.scalar(sel(Product.id).where(Product.name == "Espresso"))
    r = client.post("/api/sales", headers=admin, json={"items": [{"product_id": pid, "qty": 1}], "payments": [
        {"method": "efectivo", "amount_cents": db.scalar(sel(Product.price_cents).where(Product.id == pid))}]})
    assert r.status_code == 200, r.text
    row = db.get(Sale, r.json()["id"])
    assert row.table_id is None and row.waiter_employee_id is None


def test_effective_waiter_is_tab_then_table_then_zone(seeded, db, clock):  # noqa: F811
    client, admin = seeded
    zone_waiter, table_waiter, tab_waiter = _emp(db, "Zona"), _emp(db, "Mesa"), _emp(db, "Cuenta")
    zone = FloorZone(name="Salón", waiter_employee_id=zone_waiter.id)
    db.add(zone)
    db.commit()
    table = DiningTable(label="5", token="tok-5", zone_id=zone.id)
    db.add(table)
    db.commit()
    assert orders.effective_waiter(db, table.id) == zone_waiter.id
    table.waiter_employee_id = table_waiter.id
    db.commit()
    assert orders.effective_waiter(db, table.id) == table_waiter.id
    tab = orders.open_tab(db, table.id)
    db.commit()
    assert tab.waiter_employee_id == table_waiter.id  # copied when the account opens
    tab.waiter_employee_id = tab_waiter.id
    db.commit()
    assert orders.effective_waiter(db, table.id, tab.id) == tab_waiter.id
    assert orders.effective_waiter(db, None, tab.id) == tab_waiter.id
    tab_waiter.active = False
    db.commit()
    assert orders.effective_waiter(db, table.id, tab.id) is None  # the one in charge left: no snapshot of a ghost


def test_open_tab_copies_the_waiter_and_reassigning_does_not_touch_charged_sales(seeded, db, clock):  # noqa: F811
    client, admin = seeded
    ana, beto = _emp(db, "Ana"), _emp(db, "Beto")
    table = DiningTable(label="6", token="tok-6", waiter_employee_id=ana.id)
    db.add(table)
    db.commit()
    o = _table_order(db, table, [("Espresso", None, 1)])
    assert _status(client, admin, o.id, "received").status_code == 200
    tab_row = db.scalar(select(TableTab).where(TableTab.table_id == table.id))
    assert tab_row.waiter_employee_id == ana.id
    tab = client.get("/api/tabs", headers=admin).json()[0]
    sale = _charge(client, admin, tab)
    table.waiter_employee_id = beto.id
    db.commit()
    db.expire_all()
    assert db.get(Sale, sale["id"]).waiter_employee_id == ana.id
