"""Order screen: POS sales → orders (per channel/category), lifecycle, timers/late flags with a fake
clock, dashboard summary, metrics and the open tab per table charged as one sale."""

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import DiningTable, Order, OrderItem, Product, ProductCategory, Sale, StockItem, TableTab, User
from app.services import orders as svc
from app.services.timeutil import to_utc_naive
from tests.conftest import login
from tests.test_sizes import _sized_latte

LATTE = 340000
T0 = to_utc_naive(datetime(2026, 11, 2, 9, 0))  # Monday 09:00 local


class Clock:
    def __init__(self, t: datetime) -> None:
        self.t = t

    def __call__(self) -> datetime:
        return self.t

    def advance(self, **kw) -> None:
        self.t += timedelta(**kw)


@pytest.fixture()
def clock(monkeypatch):
    c = Clock(T0)
    monkeypatch.setattr(svc, "now", c)
    return c


def _pid(db, name: str) -> int:
    return db.scalar(select(Product.id).where(Product.name == name))


def _sale(client, h, items, total, **kw):
    return client.post("/api/sales", headers=h, json={"items": items, "payments": [{"method": "efectivo", "amount_cents": total}], **kw})


def _board(client, h) -> list[dict]:
    r = client.get("/api/orders/board", headers=h)
    assert r.status_code == 200, r.text
    return r.json()["orders"]


def _status(client, h, oid, status, **kw):
    return client.post(f"/api/orders/{oid}/status", headers=h, json={"status": status, **kw})


# ---------------------------------------------------------------- POS sale → order


def test_pos_sale_becomes_an_order_with_size_modifiers_and_notes(seeded, db, clock):
    client, admin = seeded
    pid, sz = _sized_latte(client, admin, db)
    avena = client.get("/api/modifier-groups", headers=admin).json()
    oat = next(m["id"] for g in avena for m in g["modifiers"] if m["name"] == "Bebida de avena")
    r = _sale(client, admin, [{"product_id": pid, "size_id": sz["Gr"], "modifier_ids": [oat], "notes": "bien caliente"},
                              {"product_id": _pid(db, "Medialuna"), "qty": 2}],
              420000 + 60000 + 2 * 90000, channel="salon", table_label="5")
    assert r.status_code == 200, r.text
    sale = r.json()
    orders = _board(client, admin)
    assert len(orders) == 1
    o = orders[0]
    assert o["number"] == 1 and o["status"] == "received" and o["source"] == "pos"
    assert o["sale_number"] == sale["number"] and o["table_label"] == "5" and o["channel"] == "salon"
    # Bakery (category not sent to the bar) stays out; the latte keeps size, modifiers and notes.
    assert [(i["name"], i["size_name"], i["modifiers"], i["notes"]) for i in o["items"]] == [
        ("Latte", "Grande 16 oz", ["Bebida de avena"], "bien caliente")
    ]
    assert o["target_minutes"] == 8  # salon default (latte has no prep minutes)
    # Daily numbering.
    _sale(client, admin, [{"product_id": _pid(db, "Espresso")}], 220000)
    assert [x["number"] for x in _board(client, admin)] == [1, 2]
    clock.advance(days=1)
    _sale(client, admin, [{"product_id": _pid(db, "Espresso")}], 220000)
    assert db.scalar(select(Order.number).order_by(Order.id.desc())) == 1


def test_channels_and_categories_that_skip_the_bar(seeded, db, clock):
    client, admin = seeded
    esp = _pid(db, "Espresso")
    s = client.get("/api/orders/settings", headers=admin).json()
    s["channels"]["delivery"] = False
    assert client.put("/api/orders/settings", headers=admin, json=s).status_code == 200
    assert _sale(client, admin, [{"product_id": esp}], 220000, channel="delivery").status_code == 200
    assert _board(client, admin) == []
    # Only bakery → no order at all.
    assert _sale(client, admin, [{"product_id": _pid(db, "Medialuna")}], 90000).status_code == 200
    assert _board(client, admin) == []
    # A category switched off from the catalog.
    cat = db.scalar(select(Product.category_id).where(Product.id == esp))
    assert client.patch(f"/api/product-categories/{cat}", headers=admin, json={"send_to_orders": False}).json()["send_to_orders"] is False
    _sale(client, admin, [{"product_id": esp}], 220000)
    assert _board(client, admin) == []
    # Screen disabled altogether.
    s["enabled"] = False
    client.put("/api/orders/settings", headers=admin, json=s)
    _sale(client, admin, [{"product_id": _pid(db, "Latte")}], LATTE)
    assert _board(client, admin) == []
    # Cashier can't change the settings.
    assert client.put("/api/orders/settings", headers=login(client, "Caja Demo", "1111"), json=s).status_code == 403


def test_target_is_max_of_items_or_channel_default(seeded, db, clock):
    client, admin = seeded
    assert svc.order_target([None, 3], 8) == 8
    assert svc.order_target([12, 3], 5) == 12
    assert svc.order_target([], 5) == 5
    tostado = _pid(db, "Tostado de jamón y queso")  # demo prep_minutes = 12
    _sale(client, admin, [{"product_id": tostado}, {"product_id": _pid(db, "Espresso")}], 520000 + 220000, channel="llevar")
    assert _board(client, admin)[0]["target_minutes"] == 12
    # Product prep minutes are editable from the catalog.
    r = client.patch(f"/api/products/{tostado}", headers=admin, json={"prep_minutes": 20})
    assert r.json()["prep_minutes"] == 20
    _sale(client, admin, [{"product_id": tostado}], 520000)
    assert _board(client, admin)[-1]["target_minutes"] == 20
    assert client.patch(f"/api/products/{tostado}", headers=admin, json={"prep_minutes": 0}).status_code == 422


def test_items_charged_from_a_tab_do_not_go_to_the_bar_again(seeded, db, clock):
    client, admin = seeded
    _sale(client, admin, [{"product_id": _pid(db, "Espresso"), "to_bar": False}], 220000)
    assert _board(client, admin) == []


# ---------------------------------------------------------------- lifecycle + timers


def test_lifecycle_timers_and_late_flags(seeded, db, clock):
    client, admin = seeded
    barista = login(client, "Barista Demo", "2222")
    _sale(client, admin, [{"product_id": _pid(db, "Latte")}], LATTE)  # target 8 min, warn at 75% = 6 min
    oid = _board(client, barista)[0]["id"]

    def row():
        return next(o for o in _board(client, barista) if o["id"] == oid)

    assert row()["level"] == "ok" and row()["elapsed_s"] == 0
    clock.advance(minutes=6)
    assert row()["level"] == "warn" and not row()["late"]
    assert _status(client, barista, oid, "preparing").json()["status"] == "preparing"
    clock.advance(minutes=2, seconds=1)
    r = row()
    assert r["late"] and r["level"] == "late" and r["elapsed_s"] == 8 * 60 + 1
    # Ready stops the clock; the barista is who prepared it.
    _status(client, barista, oid, "ready")
    clock.advance(minutes=30)
    r = row()
    assert r["status"] == "ready" and r["elapsed_s"] == 8 * 60 + 1 and r["prepared_by_name"] == "Barista Demo"
    # Undo "listo" and re-finish.
    assert _status(client, barista, oid, "preparing").status_code == 200
    _status(client, barista, oid, "ready")
    assert _status(client, barista, oid, "delivered").status_code == 200
    assert all(o["id"] != oid for o in _board(client, barista))
    # Invalid transitions.
    assert _status(client, barista, oid, "received").status_code == 409
    o = db.get(Order, oid)
    db.refresh(o)
    assert o.started_at == T0 + timedelta(minutes=6) and o.delivered_at is not None


def test_cancel_and_invalid_transitions(seeded, db, clock):
    client, admin = seeded
    _sale(client, admin, [{"product_id": _pid(db, "Latte")}], LATTE)
    oid = _board(client, admin)[0]["id"]
    assert _status(client, admin, oid, "delivered").status_code == 409  # must be ready first
    assert _status(client, admin, oid, "pending").status_code == 409
    r = _status(client, admin, oid, "cancelled", reason="Se fue el cliente")
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert _status(client, admin, oid, "ready").status_code == 409
    assert _board(client, admin) == []
    assert _status(client, admin, 999999, "ready").status_code == 404
    assert client.get("/api/orders/board").status_code == 401


def test_late_orders_bubble_up(seeded, db, clock):
    client, admin = seeded
    lat, esp = _pid(db, "Latte"), _pid(db, "Espresso")
    _sale(client, admin, [{"product_id": lat}], LATTE, channel="llevar")  # #1 target 5
    clock.advance(minutes=1)
    _sale(client, admin, [{"product_id": esp}], 220000, channel="delivery")  # #2 target 15
    clock.advance(minutes=1)
    _sale(client, admin, [{"product_id": esp}], 220000, channel="llevar")  # #3 target 5
    # Nothing late yet: oldest first.
    assert [o["number"] for o in _board(client, admin)] == [1, 2, 3]
    clock.advance(minutes=4)  # #1 at 6 min (late), #3 at 4 min, #2 at 5 of 15
    board = client.get("/api/orders/board", headers=admin).json()
    assert [o["number"] for o in board["orders"]] == [1, 2, 3]
    assert board["late_count"] == 1
    clock.advance(minutes=2)  # #1 at 8 (3 over), #3 at 6 (1 over)
    nums = [o["number"] for o in _board(client, admin)]
    assert nums == [1, 3, 2]
    # Ready orders go after the ones in progress.
    _status(client, admin, _board(client, admin)[0]["id"], "ready")
    assert [o["number"] for o in _board(client, admin)] == [3, 2, 1]


def test_board_drops_stale_orders(seeded, db, clock):
    client, admin = seeded
    _sale(client, admin, [{"product_id": _pid(db, "Latte")}], LATTE)
    clock.advance(hours=svc.BOARD_HOURS, minutes=1)
    assert _board(client, admin) == []


# ---------------------------------------------------------------- metrics


def _mk_order(db, *, received: datetime, prep_min: float, target: int, channel="salon", user=None, product="Latte",
              status="delivered"):
    p = db.scalar(select(Product).where(Product.name == product))
    o = Order(number=1, source="pos", status=status, channel=channel, target_minutes=target, created_at=received,
              received_at=received, ready_at=received + timedelta(minutes=prep_min) if status != "received" else None,
              prepared_by=user)
    o.items = [OrderItem(product_id=p.id, name_snapshot=p.name, qty=1)]
    db.add(o)
    db.commit()
    return o


def test_metrics_by_hour_channel_product_and_person(seeded, db, clock):
    client, admin = seeded
    barista = db.scalar(select(User.id).where(User.name == "Barista Demo"))
    caja = db.scalar(select(User.id).where(User.name == "Caja Demo"))
    nine = to_utc_naive(datetime(2026, 11, 2, 9, 10))
    ten = to_utc_naive(datetime(2026, 11, 2, 10, 5))
    _mk_order(db, received=nine, prep_min=4, target=8, user=barista)                     # on time
    _mk_order(db, received=nine, prep_min=10, target=8, user=barista)                    # late
    _mk_order(db, received=ten, prep_min=3, target=5, channel="llevar", user=caja, product="Espresso")
    _mk_order(db, received=ten, prep_min=6, target=5, channel="llevar", user=caja, product="Espresso")  # late
    _mk_order(db, received=ten, prep_min=1, target=5, status="cancelled")  # ignored
    _mk_order(db, received=ten, prep_min=0, target=5, status="received")   # unfinished: not in averages
    _mk_order(db, received=to_utc_naive(datetime(2026, 11, 1, 9, 0)), prep_min=1, target=5)  # other day

    m = svc.metrics(db, date(2026, 11, 2), date(2026, 11, 2))
    assert m["totals"] == {"orders": 4, "avg_prep_s": int((4 + 10 + 3 + 6) * 60 / 4), "late": 2, "late_pct": 50.0}
    assert [(r["label"], r["orders"], r["late"]) for r in m["by_hour"]] == [("09:00", 2, 1), ("10:00", 2, 1)]
    ch = {r["label"]: r for r in m["by_channel"]}
    assert ch["Salón"]["avg_prep_s"] == 7 * 60 and ch["Para llevar"]["avg_prep_s"] == int(4.5 * 60)
    prod = {r["label"]: r for r in m["by_product"]}
    assert prod["Latte"]["orders"] == 2 and prod["Latte"]["qty"] == 2 and prod["Espresso"]["late_pct"] == 50.0
    people = {r["label"]: r["orders"] for r in m["by_user"]}
    assert people == {"Barista Demo": 2, "Caja Demo": 2}

    # Dashboard line for that day: finished + still-open late ones.
    clock.t = ten + timedelta(minutes=30)  # the unfinished one is 30 min in (target 5): late
    s = svc.summary(db, date(2026, 11, 2), date(2026, 11, 2))
    assert s == {"orders": 4, "avg_prep_s": m["totals"]["avg_prep_s"], "late": 3, "late_pct": 50.0, "open": 1, "open_late": 1}
    d = client.get("/api/dashboard?from=2026-11-02&to=2026-11-02", headers=admin).json()
    assert d["orders"]["late"] == 3
    assert client.get("/api/dashboard?from=2026-10-01&to=2026-10-01", headers=admin).json()["orders"] is None


# ---------------------------------------------------------------- open tab per table


def _table_order(db, table: DiningTable, items: list[tuple[str, int | None, int]], status="pending") -> Order:
    o = Order(number=1, source="table", status=status, channel="salon", table_id=table.id, table_label=f"Mesa {table.label}",
              target_minutes=8, created_at=svc.now())
    for name, size_id, qty in items:
        p = db.scalar(select(Product).where(Product.name == name))
        o.items.append(OrderItem(product_id=p.id, name_snapshot=name, size_id=size_id, qty=qty, unit_price_cents=p.price_cents))
    db.add(o)
    db.commit()
    return o


def _qty(db, name: str) -> float:
    db.expire_all()
    return db.scalar(select(StockItem.current_qty).where(StockItem.name == name))


def test_confirming_opens_a_tab_and_charging_it_is_one_sale_with_stock(seeded, db, clock):
    client, admin = seeded
    pid, sz = _sized_latte(client, admin, db)
    table = DiningTable(label="4", token="tok-4")
    db.add(table)
    db.commit()
    o1 = _table_order(db, table, [("Latte", sz["Gr"], 2)])
    o2 = _table_order(db, table, [("Espresso", None, 1)])
    o3 = _table_order(db, table, [("Espresso", None, 5)])
    cajero = login(client, "Caja Demo", "1111")
    assert client.get("/api/tabs", headers=cajero).json() == []  # pending orders aren't on the tab
    board = _board(client, cajero)
    assert [o["level"] for o in board[:3]] == ["pending"] * 3
    for o in (o1, o2):
        assert _status(client, cajero, o.id, "received").status_code == 200
    _status(client, cajero, o3.id, "cancelled", reason="Pedido de más")  # rejected: never billed
    tabs = client.get("/api/tabs", headers=cajero).json()
    assert len(tabs) == 1
    tab = tabs[0]
    assert tab["table_label"] == "4" and tab["orders"] == 2 and tab["unfinished"] == 2
    assert {(ln["name"], ln["size_name"], ln["qty"]) for ln in tab["lines"]} == {("Latte", None, 2), ("Espresso", None, 1)}
    # Size name comes from the order item snapshot (None here because the test order omits it); size id is kept.
    assert next(ln for ln in tab["lines"] if ln["name"] == "Latte")["size_id"] == sz["Gr"]

    milk, coffee = _qty(db, "Leche entera"), _qty(db, "Café blend de la casa")
    total = 2 * 420000 + 220000
    items = [{"product_id": ln["product_id"], "size_id": ln["size_id"], "qty": ln["qty"], "modifier_ids": ln["modifier_ids"],
              "to_bar": False} for ln in tab["lines"]]
    r = client.post("/api/sales", headers=cajero, json={"items": items, "tab_id": tab["id"],
                                                        "payments": [{"method": "efectivo", "amount_cents": total}]})
    assert r.status_code == 200, r.text
    sale = r.json()
    assert sale["total_cents"] == total and sale["table_label"] == "Mesa 4"
    # Stock via the size recipe: Grande = ×1.5 milk (300 ml) and the 36 g coffee override, ×2.
    assert _qty(db, "Leche entera") == pytest.approx(milk - 600)
    assert _qty(db, "Café blend de la casa") == pytest.approx(coffee - 2 * 36 - 18)
    db.expire_all()
    t = db.get(TableTab, tab["id"])
    assert t.status == "closed" and t.sale_id == sale["id"]
    assert {db.get(Order, o.id).sale_id for o in (o1, o2)} == {sale["id"]}
    assert db.get(Order, o3.id).sale_id is None
    assert client.get("/api/tabs", headers=cajero).json() == []
    # No duplicate bar orders, and the tab can't be charged twice.
    assert len([o for o in _board(client, cajero) if o["source"] == "pos"]) == 0
    again = client.post("/api/sales", headers=cajero, json={"items": items, "tab_id": tab["id"],
                                                            "payments": [{"method": "efectivo", "amount_cents": total}]})
    assert again.status_code == 409
    # A new confirmed order of the same table opens a new tab.
    o4 = _table_order(db, table, [("Espresso", None, 1)])
    _status(client, cajero, o4.id, "received")
    assert [t["id"] for t in client.get("/api/tabs", headers=cajero).json()] != [tab["id"]]


def test_tab_charge_is_atomic_and_allows_courtesy(seeded, db, clock):
    client, admin = seeded
    table = DiningTable(label="7", token="tok-7")
    db.add(table)
    db.commit()
    o = _table_order(db, table, [("Espresso", None, 1)])
    _status(client, admin, o.id, "received")
    tab = client.get("/api/tabs", headers=admin).json()[0]
    items = [{"product_id": ln["product_id"], "qty": ln["qty"], "to_bar": False} for ln in tab["lines"]]
    # Wrong payment: nothing changes (tab stays open).
    bad = client.post("/api/sales", headers=admin, json={"items": items, "tab_id": tab["id"],
                                                         "payments": [{"method": "efectivo", "amount_cents": 1}]})
    assert bad.status_code == 400
    db.expire_all()
    assert db.get(TableTab, tab["id"]).status == "open"
    # Courtesy closes it without charging.
    r = client.post("/api/sales", headers=admin, json={"items": items, "tab_id": tab["id"], "is_courtesy": True,
                                                       "courtesy_reason": "Cliente habitual"})
    assert r.status_code == 200 and r.json()["is_courtesy"]
    db.expire_all()
    assert db.get(TableTab, tab["id"]).status == "closed"
    assert db.scalar(select(Sale.id).where(Sale.id == r.json()["id"])) is not None
    assert db.scalar(select(ProductCategory.send_to_orders).where(ProductCategory.name == "Panadería")) is False


# ---------------------------------------------------------------- migration


def test_migration_0005_up_and_down(seeded, tmp_path):
    import sqlite3
    from pathlib import Path

    from alembic import command

    from app.config import DB_PATH
    from app.db import engine
    from app.migrate import alembic_config

    engine.dispose()
    copy = tmp_path / "demo.db"
    src, dst = sqlite3.connect(DB_PATH), sqlite3.connect(copy)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    cfg = alembic_config()
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{Path(copy).as_posix()}")
    new = {"orders", "order_items", "dining_tables", "table_tabs", "waiter_calls"}

    def tables():
        con = sqlite3.connect(copy)
        try:
            names = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
            cols = {r[1] for r in con.execute("pragma table_info(products)")}
            n = con.execute("select count(*) from sales").fetchone()[0]
            return names, cols, n
        finally:
            con.close()

    command.stamp(cfg, "head")
    names, cols, n = tables()
    assert new <= names and "prep_minutes" in cols
    command.downgrade(cfg, "0004_product_sizes_and_details")
    names, cols, n2 = tables()
    assert not new & names and "prep_minutes" not in cols and n2 == n
    command.upgrade(cfg, "head")
    names, cols, n3 = tables()
    assert new <= names and n3 == n
    con = sqlite3.connect(copy)
    try:
        assert con.execute("select count(*) from product_categories where send_to_orders = 1").fetchone()[0] >= 1
    finally:
        con.close()


def test_free_edition_uses_channel_targets_only(seeded, db, clock):
    """Per-product prep targets are Pro (`orders_pro`): without it, the channel default rules."""
    from app.licensing import status
    from tests.conftest import pro_token

    client, admin = seeded
    status.store_token(pro_token(features=["reports"]))
    tostado = _pid(db, "Tostado de jamón y queso")  # prep 12 in the demo
    _sale(client, admin, [{"product_id": tostado}], 520000, channel="llevar")
    board = client.get("/api/orders/board", headers=admin).json()
    assert board["orders"][0]["target_minutes"] == 5 and board["pro"] is False and board["stations"] == []


def test_summary_sql_matches_the_python_aggregation(seeded, db, clock):
    """`summary` aggregates in SQL; it must give exactly what the object-by-object `_agg` gives."""
    import random

    rnd = random.Random(7)
    day = to_utc_naive(datetime(2026, 11, 2, 9, 0))
    for i in range(300):
        received = day + timedelta(minutes=rnd.randint(0, 600))
        kind = rnd.choice(["ok", "ok", "ok", "late", "cancelled", "open", "negative", "exact", "subsecond"])
        target = rnd.choice([3, 5, 8, 10])
        status = "cancelled" if kind == "cancelled" else ("received" if kind == "open" else "delivered")
        prep = {"ok": rnd.uniform(0.2, target - 0.5), "late": target + rnd.uniform(0.5, 9), "negative": -2, "exact": target,
                "subsecond": target + 0.5 / 60, "cancelled": 2, "open": 0}[kind]
        o = Order(number=i, source="pos", status=status, channel="salon", target_minutes=target, created_at=received,
                  received_at=received, ready_at=None if kind == "open" else received + timedelta(minutes=prep))
        db.add(o)
    db.commit()
    a, b = svc.range_bounds_utc(date(2026, 11, 2), date(2026, 11, 2))
    expected = svc._agg([svc._prep(o) for o in svc._finished(db, a, b)])
    got = svc._finished_stats(db, a, b)
    assert got == expected and got["orders"] > 150 and got["late"] > 20
    assert svc._finished_stats(db, *svc.range_bounds_utc(date(2025, 1, 1), date(2025, 1, 1)))["orders"] == 0
