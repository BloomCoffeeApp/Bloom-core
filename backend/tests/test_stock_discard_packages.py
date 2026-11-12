"""Quick discard (merma with reasons, whole/partial, by package or lot, from the POS) and package units."""

from datetime import date, timedelta

from sqlalchemy import select

from app.models import StockItem, StockLot, StockMovement
from app.services.stock import apply_movement
from tests.conftest import login


def _item(client, h, name="Leche entera"):
    items = client.get("/api/stock/items", headers=h).json()
    return next(i for i in items if i["name"] == name)


def _new_item(client, h, **kw):
    body = {"name": "Leche test", "unit": "ml", "avg_cost_cents": 0.15, "initial_qty": 6000} | kw
    r = client.post("/api/stock/items", json=body, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_packages_are_saved_with_one_default(seeded):
    client, h = seeded
    it = _new_item(client, h)
    r = client.put(f"/api/stock/items/{it['id']}/packages", json={"packages": [
        {"name": "Sachet 1 L", "content_qty": 1000, "barcode": "7790001", "cost_cents": 150000},
        {"name": "Caja x 12", "content_qty": 12000, "is_default": False},
    ]}, headers=h)
    assert r.status_code == 200, r.text
    pk = r.json()["packages"]
    assert [p["name"] for p in pk] == ["Sachet 1 L", "Caja x 12"]
    assert pk[0]["is_default"] and not pk[1]["is_default"]  # the first one when none is marked
    # Editing keeps ids; a second default is ignored.
    r = client.put(f"/api/stock/items/{it['id']}/packages", json={"packages": [
        {"id": pk[1]["id"], "name": "Caja x 12", "content_qty": 12000, "is_default": True},
        {"id": pk[0]["id"], "name": "Sachet 1 L", "content_qty": 1000, "is_default": True},
    ]}, headers=h)
    pk2 = r.json()["packages"]
    assert pk2[0]["id"] == pk[1]["id"] and pk2[0]["is_default"] and not pk2[1]["is_default"]
    assert client.put(f"/api/stock/items/{it['id']}/packages", json={"packages": [
        {"name": "A", "content_qty": 1}, {"name": "a", "content_qty": 2}]}, headers=h).status_code == 400
    # Stock stays in the base unit and also lists the packages.
    assert _item(client, h, "Leche test")["current_qty"] == 6000
    assert len(_item(client, h, "Leche test")["packages"]) == 2


def test_discard_by_packages_partial_and_all_with_reasons(seeded, db):
    client, h = seeded
    it = _new_item(client, h)
    pkg = client.put(f"/api/stock/items/{it['id']}/packages", json={"packages": [{"name": "Sachet 1 L", "content_qty": 1000}]},
                     headers=h).json()["packages"][0]
    r = client.post("/api/stock/waste", json={"stock_item_id": it["id"], "package_id": pkg["id"], "packages": 2,
                                               "reason_code": "expired"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["current_qty"] == 4000
    r = client.post("/api/stock/waste", json={"stock_item_id": it["id"], "qty": 250, "reason_code": "spill", "note": "Jarra"},
                    headers=h)
    assert r.json()["current_qty"] == 3750
    # Other needs a note; no amount or two amounts is rejected.
    assert client.post("/api/stock/waste", json={"stock_item_id": it["id"], "qty": 1, "reason_code": "other"}, headers=h).status_code == 422
    assert client.post("/api/stock/waste", json={"stock_item_id": it["id"], "reason_code": "spill"}, headers=h).status_code == 422
    assert client.post("/api/stock/waste", json={"stock_item_id": it["id"], "qty": 1, "all": True, "reason_code": "spill"},
                       headers=h).status_code == 422
    r = client.post("/api/stock/waste", json={"stock_item_id": it["id"], "all": True, "reason_code": "breakage"}, headers=h)
    assert r.json()["current_qty"] == 0
    # Nothing left: discarding "all" again is an error.
    assert client.post("/api/stock/waste", json={"stock_item_id": it["id"], "all": True, "reason_code": "breakage"}, headers=h).status_code == 400
    mvs = list(db.scalars(select(StockMovement).where(StockMovement.stock_item_id == it["id"], StockMovement.type == "waste")
                         .order_by(StockMovement.id)))
    assert [m.qty for m in mvs] == [-2000, -250, -3750]
    assert [m.reason for m in mvs] == ["Vencido", "Derrame / se cayó — Jarra", "Rotura"]
    # Waste is a loss: it reaches the month result.
    from app.services import expenses
    from app.services.timeutil import local_today

    res = expenses.result(db, local_today(), local_today())
    assert res["waste_cents"] >= round(6000 * 0.15)


def test_discard_from_a_specific_lot(seeded, db):
    client, h = seeded
    it = _new_item(client, h, name="Crema", initial_qty=0, track_expiry=True)
    a = StockLot(stock_item_id=it["id"], qty_remaining=500, expiry_date=date.today() + timedelta(days=2))
    b = StockLot(stock_item_id=it["id"], qty_remaining=700, expiry_date=date.today() - timedelta(days=1))
    db.add_all([a, b])
    apply_movement(db, it["id"], 1200, "purchase", unit_cost_cents=1)
    db.commit()
    lots = client.get(f"/api/stock/items/{it['id']}/lots", headers=h).json()
    assert [l["id"] for l in lots] == [b.id, a.id]  # expiring first
    r = client.post("/api/stock/waste", json={"stock_item_id": it["id"], "all": True, "lot_id": b.id, "reason_code": "expired"},
                    headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["current_qty"] == 500
    db.expire_all()
    assert db.get(StockLot, b.id).qty_remaining == 0 and db.get(StockLot, a.id).qty_remaining == 500
    assert client.post("/api/stock/waste", json={"stock_item_id": it["id"], "qty": 600, "lot_id": a.id, "reason_code": "expired"},
                       headers=h).status_code == 400


def test_quick_discard_from_pos_is_small_and_audited(seeded, db):
    client, h = seeded
    cashier = login(client, "Caja Demo", "1111")
    items = client.get("/api/stock/quick-items", headers=cashier)
    assert items.status_code == 200
    leche = next(i for i in items.json() if i["unit"] == "ml")
    before = db.get(StockItem, leche["id"]).current_qty
    r = client.post("/api/stock/quick-discard", json={"stock_item_id": leche["id"], "qty": 10}, headers=cashier)
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.get(StockItem, leche["id"]).current_qty == before - 10
    mv = db.scalar(select(StockMovement).where(StockMovement.stock_item_id == leche["id"]).order_by(StockMovement.id.desc()))
    assert mv.type == "waste" and mv.reason == "Derrame / se cayó"
    big = client.post("/api/stock/quick-discard", json={"stock_item_id": leche["id"], "qty": 5000}, headers=cashier)
    assert big.status_code == 400 and "Stock" in big.json()["detail"]
    # The full discard (Stock) still needs the stock permission.
    assert client.post("/api/stock/waste", json={"stock_item_id": leche["id"], "qty": 1, "reason_code": "spill"},
                       headers=cashier).status_code == 403
