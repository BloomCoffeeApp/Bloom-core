"""Product sizes: own price + recipe per size, POS sale snapshot, stock, voids, backward compatibility."""

import math
import sqlite3
from pathlib import Path

from sqlalchemy import select

from app.models import PriceHistory, Product, Sale, StockItem
from tests.conftest import login

LATTE = 340000


def _pid(db, name: str) -> int:
    return db.scalar(select(Product.id).where(Product.name == name))


def _stock(db, name: str) -> float:
    db.expire_all()
    return db.scalar(select(StockItem.current_qty).where(StockItem.name == name))


def _sid(db, name: str) -> int:
    return db.scalar(select(StockItem.id).where(StockItem.name == name))


def _mk_sizes(client, h) -> dict[str, int]:
    out = {}
    for i, (name, label, ml) in enumerate([("Chico 8 oz", "Ch", 240), ("Mediano 12 oz", "Me", 360), ("Grande 16 oz", "Gr", 480)]):
        r = client.post("/api/sizes", headers=h, json={"name": name, "short_label": label, "volume_ml": ml, "sort_order": i})
        assert r.status_code == 200, r.text
        out[label] = r.json()["id"]
    return out


def _sized_latte(client, h, db) -> tuple[int, dict[str, int]]:
    """Latte: Chico ×0.75 $3.000, Mediano (default) ×1 $3.400, Grande ×1.5 with a double shot (36 g) $4.200."""
    sz = _mk_sizes(client, h)
    pid = _pid(db, "Latte")
    body = {
        "sizes": [
            {"size_id": sz["Ch"], "price_cents": 300000, "recipe_scale": 0.75},
            {"size_id": sz["Me"], "price_cents": LATTE, "recipe_scale": 1, "is_default": True},
            {"size_id": sz["Gr"], "price_cents": 420000, "recipe_scale": 1.5,
             "recipe_overrides": [{"stock_item_id": _sid(db, "Café blend de la casa"), "qty": 36}]},
        ]
    }
    r = client.patch(f"/api/products/{pid}", headers=h, json=body)
    assert r.status_code == 200, r.text
    return pid, sz


def _sale(client, h, items, total, **kw):
    return client.post(
        "/api/sales", headers=h,
        json={"items": items, "payments": [{"method": "efectivo", "amount_cents": total}] if total else [], **kw},
    )


# ---------------------------------------------------------------- size list


def test_size_crud_and_permissions(seeded):
    client, admin = seeded
    cajero = login(client, "Caja Demo", "1111")
    assert client.post("/api/sizes", headers=cajero, json={"name": "Chico", "short_label": "Ch"}).status_code == 403
    r = client.post("/api/sizes", headers=admin, json={"name": " Chico 8 oz ", "short_label": "Ch", "volume_ml": 240})
    assert r.status_code == 200 and r.json()["name"] == "Chico 8 oz"
    sid = r.json()["id"]
    dup = client.post("/api/sizes", headers=admin, json={"name": "chico 8 OZ", "short_label": "C"})
    assert dup.status_code == 409
    assert client.post("/api/sizes", headers=admin, json={"name": "X", "short_label": "x", "volume_ml": 0}).status_code == 422
    r = client.patch(f"/api/sizes/{sid}", headers=admin, json={"short_label": "CH", "sort_order": 3})
    assert r.json()["short_label"] == "CH" and r.json()["sort_order"] == 3
    assert client.delete(f"/api/sizes/{sid}", headers=admin).status_code == 200
    sizes = client.get("/api/sizes", headers=cajero).json()
    assert [s["active"] for s in sizes if s["id"] == sid] == [False]
    assert all(s["id"] != sid for s in client.get("/api/sizes?include_inactive=false", headers=admin).json())


# ---------------------------------------------------------------- product sizes


def test_product_sizes_price_recipe_and_cost(seeded, db):
    client, admin = seeded
    pid, sz = _sized_latte(client, admin, db)
    p = client.get(f"/api/products/{pid}", headers=admin).json()
    assert [s["short_label"] for s in p["sizes"]] == ["Ch", "Me", "Gr"]
    assert p["price_cents"] == LATTE  # mirrors the default size
    by = {s["short_label"]: s for s in p["sizes"]}
    assert by["Me"]["is_default"] and not by["Gr"]["is_default"]
    main = ("Leche entera", "Café blend de la casa")
    recipe = lambda s: {r["stock_item_name"]: r["qty"] for r in s["recipe_items"] if r["stock_item_name"] in main}  # noqa: E731
    assert recipe(by["Ch"]) == {"Leche entera": 150, "Café blend de la casa": 13.5}
    assert recipe(by["Me"]) == {"Leche entera": 200, "Café blend de la casa": 18}
    assert recipe(by["Gr"]) == {"Leche entera": 300, "Café blend de la casa": 36}  # override beats the scale
    assert by["Ch"]["cost_cents"] < by["Me"]["cost_cents"] < by["Gr"]["cost_cents"]
    assert p["cost_cents"] == by["Me"]["cost_cents"]
    # POS catalog offers the sizes with their prices and one default.
    cajero = login(client, "Caja Demo", "1111")
    pos = next(x for x in client.get("/api/pos/catalog", headers=cajero).json()["products"] if x["id"] == pid)
    assert [(s["short_label"], s["price_cents"], s["is_default"]) for s in pos["sizes"]] == [
        ("Ch", 300000, False), ("Me", LATTE, True), ("Gr", 420000, False)
    ]
    assert client.get("/api/sizes", headers=admin).json()[0]["product_count"] == 1


def test_product_size_validation(seeded, db):
    client, admin = seeded
    sz = _mk_sizes(client, admin)
    pid = _pid(db, "Latte")
    bad = [
        [{"size_id": sz["Ch"], "price_cents": 1}, {"size_id": sz["Ch"], "price_cents": 2}],  # repeated
        [{"size_id": 9999, "price_cents": 1}],  # unknown size
        [{"size_id": sz["Ch"], "price_cents": 1, "is_default": True}, {"size_id": sz["Me"], "price_cents": 2, "is_default": True}],
        [{"size_id": sz["Ch"], "price_cents": 1, "recipe_overrides": [{"stock_item_id": 9999, "qty": 1}]}],
    ]
    for sizes in bad:
        assert client.patch(f"/api/products/{pid}", headers=admin, json={"sizes": sizes}).status_code == 400
    assert client.patch(f"/api/products/{pid}", headers=admin, json={"sizes": [{"size_id": sz["Ch"], "price_cents": -1}]}).status_code == 422
    assert client.patch(f"/api/products/{pid}", headers=admin, json={"sizes": [{"size_id": sz["Ch"], "price_cents": 1, "recipe_scale": 0}]}).status_code == 422
    # Without an explicit default, the first size (by size order) is the default.
    r = client.patch(f"/api/products/{pid}", headers=admin, json={"sizes": [
        {"size_id": sz["Gr"], "price_cents": 500000}, {"size_id": sz["Ch"], "price_cents": 250000}]})
    assert r.status_code == 200
    assert [(s["short_label"], s["is_default"]) for s in r.json()["sizes"]] == [("Ch", True), ("Gr", False)]
    assert r.json()["price_cents"] == 250000


def test_sell_grande_consumes_its_recipe_and_snapshots(seeded, db):
    client, admin = seeded
    pid, sz = _sized_latte(client, admin, db)
    leche0, cafe0 = _stock(db, "Leche entera"), _stock(db, "Café blend de la casa")
    r = _sale(client, admin, [{"product_id": pid, "size_id": sz["Gr"], "qty": 2}], 2 * 420000)
    assert r.status_code == 200, r.text
    item = r.json()["items"][0]
    assert item["size_name"] == "Grande 16 oz" and item["size_id"] == sz["Gr"]
    assert item["name_snapshot"] == "Latte" and item["unit_price_cents"] == 420000 and item["total_cents"] == 840000
    assert math.isclose(_stock(db, "Leche entera"), leche0 - 600, abs_tol=1e-6)
    assert _stock(db, "Café blend de la casa") == cafe0 - 72
    grande_cost = next(s for s in client.get(f"/api/products/{pid}", headers=admin).json()["sizes"] if s["short_label"] == "Gr")["cost_cents"]
    assert item["cost_cents"] == 2 * grande_cost

    # Price at the time of sale: changing (or renaming) the size later doesn't touch the sale.
    client.patch(f"/api/sizes/{sz['Gr']}", headers=admin, json={"name": "XL"})
    client.patch(f"/api/products/{pid}", headers=admin, json={"sizes": [{"size_id": sz["Gr"], "price_cents": 999900}]})
    detail = client.get(f"/api/sales/{r.json()['id']}", headers=admin).json()
    assert detail["items"][0]["unit_price_cents"] == 420000 and detail["items"][0]["size_name"] == "Grande 16 oz"
    hist = client.get(f"/api/products/{pid}/price-history", headers=admin).json()
    assert hist[0]["size_id"] == sz["Gr"] and hist[0]["size_name"] == "XL" and hist[0]["new_cents"] == 999900


def test_sized_product_without_size_uses_default_and_rejects_bad_sizes(seeded, db):
    client, admin = seeded
    pid, sz = _sized_latte(client, admin, db)
    r = _sale(client, admin, [{"product_id": pid}], LATTE)
    assert r.status_code == 200, r.text
    assert r.json()["items"][0]["size_name"] == "Mediano 12 oz"
    other = client.post("/api/sizes", headers=admin, json={"name": "Balde", "short_label": "B"}).json()["id"]
    n0 = db.query(Sale).count()
    assert _sale(client, admin, [{"product_id": pid, "size_id": other}], LATTE).status_code == 400
    espresso = _pid(db, "Espresso")
    assert _sale(client, admin, [{"product_id": espresso, "size_id": sz["Ch"]}], 220000).status_code == 400
    # An inactive size isn't offered nor sellable.
    client.delete(f"/api/sizes/{sz['Ch']}", headers=admin)
    assert _sale(client, admin, [{"product_id": pid, "size_id": sz["Ch"]}], 300000).status_code == 400
    pos = next(x for x in client.get("/api/pos/catalog", headers=admin).json()["products"] if x["id"] == pid)
    assert [s["short_label"] for s in pos["sizes"]] == ["Me", "Gr"]
    assert db.query(Sale).count() == n0


def test_modifier_recipe_adjustment_scales_with_the_size(seeded, db):
    """"Bebida de avena" replaces 200 ml of milk by oat drink; in a Grande (×1.5) it's 300 ml."""
    client, admin = seeded
    pid, sz = _sized_latte(client, admin, db)
    cat = client.get("/api/pos/catalog", headers=admin).json()
    latte = next(x for x in cat["products"] if x["id"] == pid)
    grp = next(g for g in latte["modifier_groups"] if g["name"] == "Tipo de leche")
    avena = next(m for m in grp["modifiers"] if m["name"] == "Bebida de avena")
    leche0, avena0 = _stock(db, "Leche entera"), _stock(db, "Bebida de avena")
    total = 420000 + avena["price_delta_cents"]
    r = _sale(client, admin, [{"product_id": pid, "size_id": sz["Gr"], "modifier_ids": [avena["id"]]}], total)
    assert r.status_code == 200, r.text
    assert r.json()["items"][0]["unit_price_cents"] == total  # size price + modifier delta on top
    assert _stock(db, "Leche entera") == leche0  # 300 − 300
    assert _stock(db, "Bebida de avena") == avena0 - 300


def test_void_courtesy_and_loyalty_with_sizes(seeded, db):
    client, admin = seeded
    pid, sz = _sized_latte(client, admin, db)
    leche0 = _stock(db, "Leche entera")
    r = _sale(client, admin, [{"product_id": pid, "size_id": sz["Ch"], "qty": 4}], 4 * 300000)
    assert math.isclose(_stock(db, "Leche entera"), leche0 - 600, abs_tol=1e-6)
    assert client.post(f"/api/sales/{r.json()['id']}/void", headers=admin, json={"reason": "error de carga"}).status_code == 200
    assert _stock(db, "Leche entera") == leche0
    # Courtesy: valued at the size's menu price, stock by the size's recipe.
    c = _sale(client, admin, [{"product_id": pid, "size_id": sz["Gr"]}], 0, is_courtesy=True)
    assert c.status_code == 200, c.text
    assert c.json()["courtesy_cents"] == 420000 and c.json()["total_cents"] == 0
    assert _stock(db, "Leche entera") == leche0 - 300
    # Loyalty points use the charged (size) price: 1 point each $1.000 by default.
    cust = client.get("/api/customers", headers=admin).json()
    cid = (cust["items"] if isinstance(cust, dict) else cust)[0]["id"]
    s = _sale(client, admin, [{"product_id": pid, "size_id": sz["Gr"], "qty": 5}], 5 * 420000, customer_id=cid)
    assert s.json()["points_earned"] == 5 * 420000 // 100000


def test_void_fallback_uses_the_sold_size_recipe(seeded, db):
    client, admin = seeded
    pid, sz = _sized_latte(client, admin, db)
    r = _sale(client, admin, [{"product_id": pid, "size_id": sz["Gr"]}], 420000)
    from app.models import StockMovement

    db.query(StockMovement).filter(StockMovement.ref_type == "sale", StockMovement.ref_id == r.json()["id"]).delete()
    db.commit()
    leche0 = _stock(db, "Leche entera")
    assert client.post(f"/api/sales/{r.json()['id']}/void", headers=admin, json={"reason": "prueba"}).status_code == 200
    assert _stock(db, "Leche entera") == leche0 + 300


def test_product_without_sizes_is_unchanged(seeded, db):
    client, admin = seeded
    pid = _pid(db, "Latte")
    p = client.get(f"/api/products/{pid}", headers=admin).json()
    assert p["sizes"] == [] and p["price_cents"] == LATTE
    leche0 = _stock(db, "Leche entera")
    r = _sale(client, admin, [{"product_id": pid}], LATTE)
    item = r.json()["items"][0]
    assert item["size_id"] is None and item["size_name"] is None and item["unit_price_cents"] == LATTE
    assert _stock(db, "Leche entera") == leche0 - 200
    # Giving it sizes and then removing them goes back to the single price.
    _, sz = _sized_latte(client, admin, db)
    r = client.patch(f"/api/products/{pid}", headers=admin, json={"sizes": [], "price_cents": 350000})
    assert r.status_code == 200 and r.json()["sizes"] == [] and r.json()["price_cents"] == 350000
    assert _sale(client, admin, [{"product_id": pid}], 350000).status_code == 200


def test_price_cents_of_sized_product_follows_sizes(seeded, db):
    client, admin = seeded
    pid, sz = _sized_latte(client, admin, db)
    r = client.patch(f"/api/products/{pid}", headers=admin, json={"price_cents": 1})
    assert r.json()["price_cents"] == LATTE  # ignored: the price lives in the sizes


def test_bulk_price_updates_each_size(seeded, db):
    client, admin = seeded
    pid, sz = _sized_latte(client, admin, db)
    cat = client.get(f"/api/products/{pid}", headers=admin).json()["category_id"]
    body = {"category_id": cat, "percent": 10, "round_to_cents": 10000}
    prev = client.post("/api/products/bulk-price", headers=admin, json={**body, "dry_run": True}).json()
    rows = [r for r in prev["items"] if r["product_id"] == pid]
    assert [(r["size_name"], r["old_cents"], r["new_cents"]) for r in rows] == [
        ("Chico 8 oz", 300000, 330000), ("Mediano 12 oz", LATTE, 370000), ("Grande 16 oz", 420000, 460000)
    ]
    client.post("/api/products/bulk-price", headers=admin, json={**body, "dry_run": False})
    p = client.get(f"/api/products/{pid}", headers=admin).json()
    assert [s["price_cents"] for s in p["sizes"]] == [330000, 370000, 460000] and p["price_cents"] == 370000
    hist = db.scalars(select(PriceHistory).where(PriceHistory.product_id == pid)).all()
    assert sorted(h.size_id for h in hist) == sorted(sz.values())


def test_dashboard_top_products_show_sizes(seeded, db):
    client, admin = seeded
    pid, sz = _sized_latte(client, admin, db)
    _sale(client, admin, [{"product_id": pid, "size_id": sz["Gr"], "qty": 30}], 30 * 420000)
    _sale(client, admin, [{"product_id": pid, "size_id": sz["Ch"], "qty": 2}], 2 * 300000)
    d = client.get("/api/dashboard", headers=admin).json()
    latte = next(t for t in d["top_products"] if t["product_id"] == pid)
    assert [(s["name"], s["qty"]) for s in latte["sizes"]] == [("Grande 16 oz", 30), ("Chico 8 oz", 2)]
    assert all(t["sizes"] == [] for t in d["top_products"] if t["product_id"] != pid)


# ---------------------------------------------------------------- customer-facing details & photo


def test_tags_featured_and_long_description(seeded, db):
    client, admin = seeded
    pid = _pid(db, "Latte")
    r = client.patch(f"/api/products/{pid}", headers=admin,
                     json={"tags": ["vegano", "sin_tacc", "vegano"], "featured": True, "long_description": "Doble shot."})
    assert r.status_code == 200
    assert r.json()["tags"] == ["sin_tacc", "vegano"] and r.json()["featured"] and r.json()["long_description"] == "Doble shot."
    assert client.patch(f"/api/products/{pid}", headers=admin, json={"tags": ["con_magia"]}).status_code == 400
    tags = client.get("/api/product-tags", headers=admin).json()
    assert {"code": "sin_tacc", "label": "Sin TACC"} in tags


def _png(w=1600, h=900, mode="RGB") -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new(mode, (w, h), (200, 120, 40) if mode == "RGB" else (200, 120, 40, 128)).save(buf, "PNG")
    return buf.getvalue()


def test_photo_upload_resizes_and_replaces(seeded, db):
    from PIL import Image

    from app.config import UPLOAD_DIR

    client, admin = seeded
    pid = _pid(db, "Latte")
    r = client.put(f"/api/products/{pid}/photo", headers={**admin, "Content-Type": "image/png"}, content=_png())
    assert r.status_code == 200, r.text
    url = r.json()["image_url"]
    assert url.startswith("/uploads/products/") and url.endswith(".webp")
    f = UPLOAD_DIR / url.removeprefix("/uploads/")
    with Image.open(f) as img:
        assert img.format == "WEBP" and max(img.size) == 1200
    assert client.get(url).status_code == 200
    # Replacing deletes the old file; RGBA works too.
    r2 = client.put(f"/api/products/{pid}/photo", headers={**admin, "Content-Type": "image/png"}, content=_png(300, 300, "RGBA"))
    assert r2.status_code == 200 and not f.exists()
    f2 = UPLOAD_DIR / r2.json()["image_url"].removeprefix("/uploads/")
    assert client.delete(f"/api/products/{pid}/photo", headers=admin).json()["image_url"] is None
    assert not f2.exists()


def test_photo_upload_validation(seeded, db):
    client, admin = seeded
    pid = _pid(db, "Latte")
    cajero = login(client, "Caja Demo", "1111")
    put = lambda body, ctype, h=admin: client.put(f"/api/products/{pid}/photo", headers={**h, "Content-Type": ctype}, content=body)  # noqa: E731
    assert put(_png(), "image/png", cajero).status_code == 403
    assert put(b"not an image at all", "image/png").status_code == 415
    assert put(_png(), "image/gif").status_code == 415
    assert put(b"<svg xmlns='http://www.w3.org/2000/svg'/>", "image/svg+xml").status_code == 415
    assert put(b"", "image/png").status_code == 400
    assert put(b"x" * (8 * 1024 * 1024 + 1), "image/jpeg").status_code == 413
    assert client.put("/api/products/99999/photo", headers={**admin, "Content-Type": "image/png"}, content=_png()).status_code == 404
    assert db.get(Product, pid).image_path is None


def test_image_path_cannot_be_set_through_the_api(seeded, db):
    client, admin = seeded
    pid = _pid(db, "Latte")
    client.patch(f"/api/products/{pid}", headers=admin, json={"image_path": "../../secret.db"})
    db.expire_all()
    assert db.get(Product, pid).image_path is None


# ---------------------------------------------------------------- migration


def test_migration_0004_up_and_down_keeps_demo_data(seeded, tmp_path):
    """Upgrade/downgrade on a copy of a DB with demo data: purely additive, nothing else changes."""
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

    def snapshot():
        con = sqlite3.connect(copy)
        try:
            tables = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
            cols = {r[1] for r in con.execute("pragma table_info(sale_items)")}
            data = (
                con.execute("select id, name, price_cents, description from products order by id").fetchall(),
                con.execute("select id, sale_id, product_id, name_snapshot, unit_price_cents, cost_cents from sale_items order by id").fetchall(),
                con.execute("select count(*) from sales").fetchone(),
            )
            return tables, cols, data
        finally:
            con.close()

    command.stamp(cfg, "head")
    before_tables, before_cols, before = snapshot()
    assert {"sizes", "product_sizes", "product_size_recipe_items"} <= before_tables

    command.downgrade(cfg, "0003_sale_courtesy")
    t, cols, data = snapshot()
    assert not {"sizes", "product_sizes", "product_size_recipe_items"} & t
    assert "size_id" not in cols and "size_name" not in cols
    assert data == before

    command.upgrade(cfg, "head")
    t, cols, data = snapshot()
    assert t == before_tables and {"size_id", "size_name"} <= cols and data == before
    con = sqlite3.connect(copy)
    try:
        assert con.execute("select count(*) from product_sizes").fetchone() == (0,)
        assert con.execute("select count(*) from sale_items where size_id is not null").fetchone() == (0,)
        assert con.execute("select count(*) from products where featured != 0").fetchone() == (0,)
    finally:
        con.close()

