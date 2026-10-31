from sqlalchemy import select

from app.models import Product
from tests.conftest import login

LATTE = 340000


def _latte(db) -> int:
    return db.scalar(select(Product.id).where(Product.name == "Latte"))


def test_open_twice_is_conflict(seeded):
    client, admin = seeded
    # Demo data leaves one session open today.
    assert client.get("/api/cash/current", headers=admin).json() is not None
    assert client.post("/api/cash/open", json={"opening_cents": 100}, headers=admin).status_code == 409


def test_arqueo_expected_vs_counted(seeded, db):
    client, admin = seeded
    assert client.post("/api/cash/close", json={"counts": []}, headers=admin).status_code == 200
    assert client.get("/api/cash/current", headers=admin).json() is None
    assert client.post("/api/cash/movements", json={"type": "in", "amount_cents": 100, "reason": "x"}, headers=admin).status_code == 409

    cajero = login(client, "Caja Demo", "1111")
    r = client.post("/api/cash/open", json={"opening_cents": 1000000}, headers=cajero)
    assert r.status_code == 200 and r.json()["expected_cash_cents"] == 1000000
    sid = r.json()["id"]

    item = [{"product_id": _latte(db), "qty": 1}]
    s1 = client.post("/api/sales", json={"items": item, "payments": [{"method": "efectivo", "amount_cents": LATTE, "tendered_cents": 500000}]}, headers=cajero)
    assert s1.status_code == 200
    client.post("/api/sales", json={"items": item, "payments": [{"method": "qr", "amount_cents": LATTE}]}, headers=cajero)
    s3 = client.post("/api/sales", json={"items": item, "payments": [{"method": "debito", "amount_cents": LATTE}]}, headers=cajero).json()
    enc = login(client, "Encargado Demo", "3333")
    client.post(f"/api/sales/{s3['id']}/void", json={"reason": "cliente se arrepintió"}, headers=enc)
    assert client.post("/api/cash/movements", json={"type": "in", "amount_cents": 200000, "reason": "Cambio"}, headers=cajero).status_code == 200
    assert client.post("/api/cash/movements", json={"type": "out", "amount_cents": 50000, "reason": "Hielo"}, headers=cajero).status_code == 200

    cur = client.get("/api/cash/current", headers=cajero).json()
    expected_cash = 1000000 + LATTE + 200000 - 50000  # change already netted out
    assert cur["expected_cash_cents"] == expected_cash
    by = {m["method"]: m for m in cur["by_method"]}
    assert by["qr"]["expected_cents"] == LATTE
    assert "debito" not in by or by["debito"]["expected_cents"] == 0  # voided sale excluded
    assert cur["tickets"] == 2 and cur["voided_count"] == 1
    assert len(cur["movements"]) == 2

    r = client.post(
        "/api/cash/close",
        json={"counts": [{"payment_method": "efectivo", "counted_cents": expected_cash - 10000}, {"payment_method": "qr", "counted_cents": LATTE}], "notes": "faltan $100"},
        headers=cajero,
    )
    assert r.status_code == 200, r.text
    z = r.json()
    assert z["status"] == "closed" and z["difference_cents"] == -10000
    zb = {m["method"]: m for m in z["by_method"]}
    assert zb["efectivo"]["difference_cents"] == -10000 and zb["qr"]["difference_cents"] == 0
    assert z["by_category"][0]["name"] == "Con leche"

    detail = client.get(f"/api/cash/sessions/{sid}", headers=admin).json()
    assert detail["expected_cash_cents"] == expected_cash and detail["notes"] == "faltan $100"
    hist = client.get("/api/cash/sessions", headers=admin).json()
    assert hist[0]["id"] == sid and hist[0]["difference_cents"] == -10000 and hist[0]["tickets"] == 2
