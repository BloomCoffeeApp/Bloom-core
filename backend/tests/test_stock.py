import math

from app.db import SessionLocal
from app.services.stock import apply_movement
from app.services.stock_ops import daily_consumption
from tests.conftest import login


def _item(client, headers, name):
    return next(i for i in client.get("/api/stock/items", headers=headers).json() if i["name"] == name)


def test_items_status_and_summary(seeded):
    client, admin = seeded
    blend = _item(client, admin, "Café blend de la casa")
    assert blend["value_cents"] == round(max(blend["current_qty"], 0) * blend["avg_cost_cents"])
    items = client.get("/api/stock/items", headers=admin).json()
    s = client.get("/api/stock/summary", headers=admin).json()
    assert s["low_count"] == sum(1 for i in items if i["status"] == "low")
    assert s["out_count"] == sum(1 for i in items if i["status"] == "out")
    assert s["total_value_cents"] == sum(i["value_cents"] for i in items)
    leche = _item(client, admin, "Leche entera")
    client.post("/api/stock/adjust", headers=admin, json={"stock_item_id": leche["id"], "new_qty": 0, "reason": "x"})
    assert _item(client, admin, "Leche entera")["status"] == "out"
    client.post("/api/stock/adjust", headers=admin, json={"stock_item_id": leche["id"], "new_qty": leche["min_qty"], "reason": "x"})
    assert _item(client, admin, "Leche entera")["status"] == "low"
    client.post("/api/stock/adjust", headers=admin, json={"stock_item_id": leche["id"], "new_qty": leche["min_qty"] * 3, "reason": "x"})
    assert _item(client, admin, "Leche entera")["status"] == "ok"
    assert any(i["id"] == leche["id"] for i in client.get("/api/stock/items?status=ok", headers=admin).json())


def test_adjust_and_waste_create_movements_and_audit(seeded):
    client, admin = seeded
    leche = _item(client, admin, "Leche entera")
    r = client.post("/api/stock/adjust", headers=admin, json={"stock_item_id": leche["id"], "new_qty": 20000, "reason": "Recuento"})
    assert r.status_code == 200, r.text
    assert r.json()["current_qty"] == 20000
    r = client.post("/api/stock/adjust", headers=admin, json={"stock_item_id": leche["id"], "delta": 500, "reason": "Error carga"})
    assert r.json()["current_qty"] == 20500
    assert client.post("/api/stock/adjust", headers=admin,
                       json={"stock_item_id": leche["id"], "delta": 1, "new_qty": 3, "reason": "x"}).status_code == 422
    r = client.post("/api/stock/waste", headers=admin, json={"stock_item_id": leche["id"], "qty": 1000, "reason": "Vencida"})
    assert r.json()["current_qty"] == 19500
    kardex = client.get(f"/api/stock/items/{leche['id']}/movements", headers=admin).json()
    assert [m["type"] for m in kardex[:3]] == ["waste", "adjustment", "adjustment"]
    assert kardex[0]["qty"] == -1000 and kardex[0]["balance_after"] == 19500
    assert kardex[0]["reason"] == "Vencida" and kardex[0]["user_name"] == "Admin"


def test_permissions(seeded):
    client, _ = seeded
    barista = login(client, "Barista Demo", "2222")
    cajero = login(client, "Caja Demo", "1111")
    encargado = login(client, "Encargado Demo", "3333")
    assert client.get("/api/stock/items", headers=barista).status_code == 200
    assert client.get("/api/stock/items", headers=cajero).status_code == 403
    item = _item(client, barista, "Leche entera")
    body = {"stock_item_id": item["id"], "qty": 10, "reason": "x"}
    assert client.post("/api/stock/waste", headers=barista, json=body).status_code == 403
    assert client.post("/api/stock/waste", headers=encargado, json=body).status_code == 200


def test_physical_count_applies_differences(seeded):
    client, admin = seeded
    cats = client.get("/api/stock/categories", headers=admin).json()
    lact = next(c for c in cats if c["name"] == "Lácteos")
    c = client.post("/api/stock/counts", headers=admin, json={"category_id": lact["id"]}).json()
    assert c["status"] == "open" and c["total_items"] == 3
    leche = next(i for i in c["items"] if i["name"] == "Leche entera")
    avena = next(i for i in c["items"] if i["name"] == "Bebida de avena")
    crema_before = _item(client, admin, "Crema de leche")["current_qty"]
    assert leche["expected_qty"] == _item(client, admin, "Leche entera")["current_qty"]
    counted = max(leche["expected_qty"] - 1000, 0) + 7
    r = client.patch(f"/api/stock/counts/{c['id']}/items/{leche['id']}", headers=admin, json={"counted_qty": counted})
    diff = next(i for i in r.json()["items"] if i["id"] == leche["id"])["diff_qty"]
    assert diff == round(counted - leche["expected_qty"], 4)
    r = client.patch(f"/api/stock/counts/{c['id']}/items", headers=admin,
                     json={"items": [{"id": avena["id"], "counted_qty": max(avena["expected_qty"], 0)}]})
    assert r.json()["counted_items"] == 2
    r = client.post(f"/api/stock/counts/{c['id']}/apply", headers=admin)
    assert r.status_code == 200 and r.json()["status"] == "applied"
    assert _item(client, admin, "Leche entera")["current_qty"] == counted
    assert _item(client, admin, "Bebida de avena")["current_qty"] == max(avena["expected_qty"], 0)
    assert _item(client, admin, "Crema de leche")["current_qty"] == crema_before  # not counted → untouched
    kardex = client.get(f"/api/stock/items/{leche['stock_item_id']}/movements", headers=admin).json()
    assert kardex[0]["type"] == "count" and kardex[0]["qty"] == diff
    assert client.post(f"/api/stock/counts/{c['id']}/apply", headers=admin).status_code == 409
    assert len(client.get("/api/stock/counts", headers=admin).json()) == 1


def test_suggestions_by_supplier(seeded):
    client, admin = seeded
    med = _item(client, admin, "Medialuna de manteca")  # unit item, min 24
    with SessionLocal() as db:
        base = daily_consumption(db).get(med["id"], 0.0)
        # extra 140 sold inside the 14-day window → +10/day
        apply_movement(db, med["id"], -140, "sale")
        db.commit()
    cur = round(med["current_qty"] - 140, 4)
    assert cur <= med["min_qty"]
    groups = client.get("/api/stock/suggestions", headers=admin).json()
    pan = next(g for g in groups if g["supplier_name"].startswith("Panadería"))
    s = next(i for i in pan["items"] if i["stock_item_id"] == med["id"])
    assert s["status"] == ("out" if cur <= 0 else "low")
    assert abs(s["daily_consumption"] - round(base + 10, 3)) < 1e-6
    assert s["suggested_qty"] == math.ceil(max(24 * 2 - cur, (base + 10) * 7 - cur) - 1e-9)
    assert pan["total_est_cents"] == sum(i["est_cost_cents"] for i in pan["items"])
