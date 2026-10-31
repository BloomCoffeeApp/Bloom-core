from app.db import SessionLocal
from app.models import Product
from app.services import recipes
from app.services.catalog import round_price
from tests.conftest import login


def _product(client, headers, name):
    return next(p for p in client.get("/api/products", headers=headers).json() if p["name"] == name)


def test_round_price():
    assert round_price(242000, 5000) == 240000
    assert round_price(242500, 5000) == 245000
    assert round_price(1234.4, 0) == 1234


def test_product_cost_and_margin_from_demo_recipe(seeded):
    client, admin = seeded
    latte = _product(client, admin, "Latte")
    # 18 g blend @280 + 200 ml milk @12 + 1 cup @12000 + 1 lid @4000
    assert latte["cost_cents"] == 18 * 280 + 200 * 12 + 12000 + 4000
    assert latte["margin_pct"] == round((340000 - latte["cost_cents"]) / 340000 * 100, 1)
    assert latte["category"]["name"] == "Con leche"
    assert len(latte["recipe_items"]) == 4
    assert len(latte["modifier_group_ids"]) == 2
    with SessionLocal() as db:
        assert recipes.cost_cents(db, db.get(Product, latte["id"])) == latte["cost_cents"]
    medialuna = _product(client, admin, "Medialuna")
    assert medialuna["cost_cents"] == 35000  # resold item, direct stock link


def test_create_update_product_records_price_history(seeded):
    client, admin = seeded
    items = client.get("/api/stock/items", headers=admin).json()
    blend = next(i for i in items if i["name"] == "Café blend de la casa")
    cat = client.get("/api/product-categories", headers=admin).json()[0]
    r = client.post(
        "/api/products",
        headers=admin,
        json={"name": "Ristretto", "category_id": cat["id"], "price_cents": 200000,
              "recipe_items": [{"stock_item_id": blend["id"], "qty": 15}]},
    )
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["cost_cents"] == 15 * 280
    r = client.patch(f"/api/products/{p['id']}", headers=admin, json={"price_cents": 250000})
    assert r.json()["price_cents"] == 250000
    hist = client.get(f"/api/products/{p['id']}/price-history", headers=admin).json()
    assert len(hist) == 1 and hist[0]["old_cents"] == 200000 and hist[0]["new_cents"] == 250000
    # delete = deactivate
    assert client.delete(f"/api/products/{p['id']}", headers=admin).status_code == 200
    assert all(x["id"] != p["id"] for x in client.get("/api/products", headers=admin).json())
    assert any(x["id"] == p["id"] for x in client.get("/api/products?include_inactive=true", headers=admin).json())


def test_bulk_price_with_rounding_and_history(seeded):
    client, admin = seeded
    cats = client.get("/api/product-categories", headers=admin).json()
    cafe = next(c for c in cats if c["name"] == "Cafetería")
    body = {"category_id": cafe["id"], "percent": 10, "round_to_cents": 5000}
    preview = client.post("/api/products/bulk-price", headers=admin, json={**body, "dry_run": True}).json()
    assert preview["applied"] is False
    esp = next(i for i in preview["items"] if i["name"] == "Espresso")
    assert esp["old_cents"] == 220000 and esp["new_cents"] == 240000  # 242000 → nearest $50
    assert _product(client, admin, "Espresso")["price_cents"] == 220000  # untouched by preview

    r = client.post("/api/products/bulk-price", headers=admin, json=body)
    assert r.status_code == 200 and r.json()["applied"]
    assert _product(client, admin, "Espresso")["price_cents"] == 240000
    assert _product(client, admin, "Latte")["price_cents"] == 340000  # other category untouched
    hist = client.get(f"/api/products/{esp['product_id']}/price-history", headers=admin).json()
    assert hist[0]["old_cents"] == 220000 and hist[0]["new_cents"] == 240000


def test_pos_catalog_shape(seeded):
    client, _ = seeded
    cajero = login(client, "Caja Demo", "1111")
    data = client.get("/api/pos/catalog", headers=cajero).json()
    assert set(data["categories"][0]) == {"id", "name", "color", "icon"}
    latte = next(p for p in data["products"] if p["name"] == "Latte")
    assert set(latte) == {"id", "name", "price_cents", "category_id", "color", "image_path", "modifier_groups"}
    grp = next(g for g in latte["modifier_groups"] if g["name"] == "Tipo de leche")
    assert set(grp) == {"id", "name", "min_select", "max_select", "modifiers"}
    assert {m["name"] for m in grp["modifiers"]} == {"Leche entera", "Bebida de avena"}
    assert set(grp["modifiers"][0]) == {"id", "name", "price_delta_cents"}
    # cashier can't edit prices
    assert client.patch(f"/api/products/{latte['id']}", headers=cajero, json={"price_cents": 1}).status_code == 403


def test_modifier_group_crud(seeded):
    client, admin = seeded
    items = client.get("/api/stock/items", headers=admin).json()
    leche = next(i for i in items if i["name"] == "Leche entera")
    r = client.post(
        "/api/modifier-groups",
        headers=admin,
        json={"name": "Tamaño", "min_select": 1, "max_select": 1,
              "modifiers": [{"name": "Chico"}, {"name": "Grande", "price_delta_cents": 50000,
                                                 "recipe_items": [{"stock_item_id": leche["id"], "qty_delta": 100}]}]},
    )
    assert r.status_code == 200, r.text
    g = r.json()
    assert [m["name"] for m in g["modifiers"]] == ["Chico", "Grande"]
    grande = g["modifiers"][1]
    r = client.patch(f"/api/modifier-groups/{g['id']}", headers=admin,
                     json={"modifiers": [{"id": grande["id"], "name": "Grande 16oz", "price_delta_cents": 60000}]})
    g2 = r.json()
    assert len(g2["modifiers"]) == 1 and g2["modifiers"][0]["id"] == grande["id"]
    assert g2["modifiers"][0]["recipe_items"] == []
    assert client.post("/api/modifier-groups", headers=admin, json={"name": "x", "min_select": 3, "max_select": 1}).status_code == 400
    assert client.delete(f"/api/modifier-groups/{g['id']}", headers=admin).status_code == 200
