"""Supplies by channel ("Insumos según el canal"): per category default, per product, per size override,
consumed with the sale in each channel and restored by a void."""

from sqlalchemy import select

from app.models import Product, StockItem
from tests.conftest import login
from tests.test_sizes import _mk_sizes

MEDIALUNA = 90000


def _pid(db, name):
    return db.scalar(select(Product.id).where(Product.name == name))


def _sid(db, name):
    return db.scalar(select(StockItem.id).where(StockItem.name == name))


def _qty(db, name):
    db.expire_all()
    return db.scalar(select(StockItem.current_qty).where(StockItem.name == name))


def _sale(client, h, items, total, channel):
    r = client.post("/api/sales", headers=h, json={
        "items": items, "channel": channel, "payments": [{"method": "efectivo", "amount_cents": total}]})
    assert r.status_code == 200, r.text
    return r.json()


def _row(channel, sid, qty=1, size_id=None):
    return {"channel": channel, "stock_item_id": sid, "qty": qty, "size_id": size_id}


def test_empty_by_default_nothing_extra_is_consumed(seeded, db):
    client, admin = seeded
    pid = _pid(db, "Medialuna")
    out = client.get(f"/api/products/{pid}/channel-supplies", headers=admin).json()
    assert out["rows"] == [] and out["inherited"] is False
    before = {n: _qty(db, n) for n in ("Vaso térmico 8oz", "Tapa para vaso", "Sobre de azúcar")}
    _sale(client, admin, [{"product_id": pid}], MEDIALUNA, "delivery")
    assert {n: _qty(db, n) for n in before} == before


def test_each_channel_has_its_own_list_from_the_category_default(seeded, db):
    client, admin = seeded
    pid = _pid(db, "Medialuna")
    cat = db.get(Product, pid).category_id
    vaso, tapa, azucar = _sid(db, "Vaso térmico 8oz"), _sid(db, "Tapa para vaso"), _sid(db, "Sobre de azúcar")
    rows = [_row("salon", azucar, 2), _row("llevar", vaso), _row("llevar", tapa), _row("delivery", vaso), _row("delivery", tapa),
            _row("delivery", azucar, 1)]
    r = client.put(f"/api/product-categories/{cat}/channel-supplies", headers=admin, json={"rows": rows})
    assert r.status_code == 200, r.text
    assert client.get(f"/api/products/{pid}/channel-supplies", headers=admin).json()["inherited"] is True

    def snap():
        return _qty(db, "Vaso térmico 8oz"), _qty(db, "Tapa para vaso"), _qty(db, "Sobre de azúcar")

    v0, t0, a0 = snap()
    _sale(client, admin, [{"product_id": pid, "qty": 2}], 2 * MEDIALUNA, "salon")
    assert snap() == (v0, t0, a0 - 4)
    _sale(client, admin, [{"product_id": pid, "qty": 2}], 2 * MEDIALUNA, "llevar")  # counter take away
    assert snap() == (v0 - 2, t0 - 2, a0 - 4)
    sale = _sale(client, admin, [{"product_id": pid}], MEDIALUNA, "delivery")
    assert snap() == (v0 - 3, t0 - 3, a0 - 5)
    # Voiding the sale gives the supplies back with the rest of its stock movements.
    assert client.post(f"/api/sales/{sale['id']}/void", headers=admin, json={"reason": "Error"}).status_code == 200
    assert snap() == (v0 - 2, t0 - 2, a0 - 4)


def test_product_list_overrides_category_and_sizes_override_the_base(seeded, db):
    client, admin = seeded
    sz = _mk_sizes(client, admin)
    pid = _pid(db, "Medialuna")
    cat = db.get(Product, pid).category_id
    v8, v12, tapa = _sid(db, "Vaso térmico 8oz"), _sid(db, "Vaso térmico 12oz"), _sid(db, "Tapa para vaso")
    client.put(f"/api/product-categories/{cat}/channel-supplies", headers=admin, json={"rows": [_row("llevar", tapa, 5)]})
    # Product: base 8 oz cup + lid; the 12 oz size swaps the cup (8 oz → 0, 12 oz → 1).
    body = {"rows": [_row("llevar", v8), _row("llevar", tapa), _row("llevar", v8, 0, sz["Me"]), _row("llevar", v12, 1, sz["Me"])]}
    out = client.put(f"/api/products/{pid}/channel-supplies", headers=admin, json=body).json()
    assert out["inherited"] is False and len(out["rows"]) == 4
    from app.models import ChannelSupply
    from app.services import channel_supplies

    rows = list(db.scalars(select(ChannelSupply).where(ChannelSupply.product_id == pid)))
    assert channel_supplies.per_unit(rows, "llevar", None) == {v8: 1, tapa: 1}
    assert channel_supplies.per_unit(rows, "llevar", sz["Me"]) == {tapa: 1, v12: 1}
    assert channel_supplies.per_unit(rows, "salon", sz["Me"]) == {}
    p = db.get(Product, pid)
    assert channel_supplies.consumption(db, "llevar", [(p, sz["Me"], 3), (p, None, 1)]) == {v8: 1, tapa: 4, v12: 3}
    # Clearing the product's list falls back to the category default again.
    assert client.put(f"/api/products/{pid}/channel-supplies", headers=admin, json={"rows": []}).json()["inherited"] is True


def test_validation_and_permissions(seeded, db):
    client, admin = seeded
    pid = _pid(db, "Medialuna")
    vaso = _sid(db, "Vaso térmico 8oz")
    bad = client.put(f"/api/products/{pid}/channel-supplies", headers=admin, json={"rows": [_row("llevar", 999999)]})
    assert bad.status_code == 400
    dup = client.put(f"/api/products/{pid}/channel-supplies", headers=admin, json={"rows": [_row("llevar", vaso), _row("llevar", vaso)]})
    assert dup.status_code == 400
    assert client.put(f"/api/products/{pid}/channel-supplies", headers=admin, json={"rows": [_row("mesa", vaso)]}).status_code == 422
    cajero = login(client, "Caja Demo", "1111")
    assert client.put(f"/api/products/{pid}/channel-supplies", headers=cajero, json={"rows": []}).status_code == 403
