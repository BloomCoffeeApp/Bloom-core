"""Direct printing: configuration, tickets/Z/test page through a fake transport, cash drawer, kitchen
tickets per station sent after the commit (never on rollback), fallbacks (no printer, failures, demo /
non-Windows) and the real raw-TCP transport against a local socket."""

import socket
import threading

import pytest
from sqlalchemy import select

from app.models import OrderStation, Product, ProductCategory
from app.services import printers, printing
from app.services.printers import PrintError
from tests.conftest import login

ESC = b"\x1b"
LATTE = 340000


class FakeTransport:
    def __init__(self) -> None:
        self.jobs: list[tuple[str, bytes, str]] = []
        self.fail: str | None = None

    def __call__(self, p):
        def send(data: bytes, doc: str) -> None:
            if self.fail:
                raise PrintError(self.fail)
            self.jobs.append((p["name"], data, doc))

        return send


@pytest.fixture()
def fake(monkeypatch):
    t = FakeTransport()
    monkeypatch.setattr(printing, "transport", t)
    monkeypatch.setattr(printers, "IS_WINDOWS", True)  # availability() is per platform
    monkeypatch.setattr(printing, "run_async", False)
    printing._failures.clear()
    return t


def _printer(name="Caja", **kw):
    return {"name": name, "kind": "network", "target": "192.168.0.50", "port": 9100, "paper_mm": 80, "chars": 48,
            "codepage": "cp858", "cut": "partial", "feed_lines": 4} | kw


def _configure(client, h, **kw):
    body = {"printers": [_printer()], "cashier_printer": None, "ticket_mode": "auto", "cash_drawer": True} | kw
    r = client.put("/api/printing/config", headers=h, json=body)
    assert r.status_code == 200, r.text
    cfg = r.json()
    if body.get("cashier_printer") is None and cfg["printers"]:
        cfg = client.put("/api/printing/config", headers=h, json={**cfg, "cashier_printer": cfg["printers"][0]["id"]}).json()
    return cfg


def _pid(db, name):
    return db.scalar(select(Product.id).where(Product.name == name))


def _sale(client, h, db, method="efectivo", product="Latte", total=LATTE):
    r = client.post("/api/sales", headers=h, json={"items": [{"product_id": _pid(db, product)}],
                                                  "payments": [{"method": method, "amount_cents": total}]})
    assert r.status_code == 200, r.text
    return r.json()


def test_config_roundtrip_ids_and_permissions(seeded, fake):
    client, admin = seeded
    cajero = login(client, "Caja Demo", "1111")
    cfg = client.get("/api/printing/config", headers=admin).json()
    assert cfg["printers"] == [] and cfg["ticket_mode"] == "ask" and cfg["available"] is True and cfg["station_list"] == []
    assert client.get("/api/printing/config", headers=cajero).status_code == 403
    assert client.put("/api/printing/config", headers=cajero, json={}).status_code == 403
    st = client.get("/api/printing/status", headers=cajero).json()
    assert st == {"available": True, "reason": None, "ticket_mode": "ask", "cashier": False, "cash_drawer": False}

    body = {"printers": [_printer(), _printer("Cocina", kind="windows", target="POS-80", paper_mm=58, chars=32)],
            "cashier_printer": "nope", "ticket_mode": "auto", "stations": {"1": "nope"}}
    cfg = client.put("/api/printing/config", headers=admin, json=body).json()
    ids = [p["id"] for p in cfg["printers"]]
    assert all(ids) and len(set(ids)) == 2
    assert cfg["cashier_printer"] is None and cfg["stations"] == {}  # unknown printers are dropped
    cfg = client.put("/api/printing/config", headers=admin, json={**cfg, "cashier_printer": ids[0], "stations": {"1": ids[1]}}).json()
    assert cfg["cashier_printer"] == ids[0] and cfg["stations"] == {"1": ids[1]} and [p["id"] for p in cfg["printers"]] == ids
    st = client.get("/api/printing/status", headers=cajero).json()
    assert st["cashier"] is True and st["ticket_mode"] == "auto"
    # Validation: bad code page / width / empty target.
    bad = {**body, "printers": [_printer(codepage="utf8")]}
    assert client.put("/api/printing/config", headers=admin, json=bad).status_code == 422
    assert client.put("/api/printing/config", headers=admin, json={**body, "printers": [_printer(chars=10)]}).status_code == 422
    assert client.put("/api/printing/config", headers=admin, json={**body, "printers": [_printer(target="  ")]}).status_code == 422


def test_ticket_without_printer_is_409_so_the_front_uses_the_dialog(seeded, db, fake):
    client, admin = seeded
    sale = _sale(client, admin, db)
    r = client.post(f"/api/printing/sales/{sale['id']}/ticket", headers=admin, json={})
    assert r.status_code == 409 and "impresora de caja" in r.json()["detail"]
    assert fake.jobs == []


def test_ticket_drawer_and_failures(seeded, db, fake):
    client, admin = seeded
    cajero = login(client, "Caja Demo", "1111")
    _configure(client, admin)
    sale = _sale(client, cajero, db)
    r = client.post(f"/api/printing/sales/{sale['id']}/ticket", headers=cajero, json={"open_drawer": True})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "printer": "Caja", "drawer": True}
    name, data, doc = fake.jobs[-1]
    assert name == "Caja" and doc == f"Ticket {sale['number']}"
    assert data.startswith(ESC + b"@" + ESC + b"t\x13" + ESC + b"p\x00")  # drawer kick before printing
    assert f"Ticket #{sale['number']}".encode() in data and "Café Test".encode("cp858") in data and b"Latte" in data
    # Reprint: never opens the drawer.
    client.post(f"/api/printing/sales/{sale['id']}/ticket", headers=cajero, json={"open_drawer": False})
    assert ESC + b"p" not in fake.jobs[-1][1]
    # Not cash: no drawer even if asked.
    qr = _sale(client, cajero, db, method="qr")
    assert client.post(f"/api/printing/sales/{qr['id']}/ticket", headers=cajero, json={"open_drawer": True}).json()["drawer"] is False
    # Drawer alone (ticket mode "ask"/"never").
    assert client.post(f"/api/printing/sales/{sale['id']}/drawer", headers=cajero).json()["drawer"] is True
    assert fake.jobs[-1][1] == ESC + b"@" + ESC + b"p\x00\x19\xfa"
    assert client.post(f"/api/printing/sales/{qr['id']}/drawer", headers=cajero).json()["drawer"] is False
    # Printer fails: 502 with a clear message (the front falls back to the dialog).
    fake.fail = "La impresora 192.168.0.50:9100 no respondió."
    r = client.post(f"/api/printing/sales/{sale['id']}/ticket", headers=cajero, json={})
    assert r.status_code == 502 and r.json()["detail"] == "No se pudo imprimir en «Caja»: La impresora 192.168.0.50:9100 no respondió."
    assert client.post("/api/printing/sales/999999/ticket", headers=cajero, json={}).status_code in (404, 502)


def test_delivery_ticket_prints_the_shipping_line(seeded, db, fake):
    client, admin = seeded
    _configure(client, admin)
    r = client.post("/api/sales", headers=admin, json={
        "items": [{"product_id": _pid(db, "Latte")}], "channel": "delivery", "delivery_fee_cents": 50000,
        "payments": [{"method": "efectivo", "amount_cents": LATTE + 50000}]})
    assert r.status_code == 200, r.text
    sale = r.json()
    assert client.post(f"/api/printing/sales/{sale['id']}/ticket", headers=admin, json={}).status_code == 200
    text = fake.jobs[-1][1].decode("cp858", errors="replace")
    assert "Envío" in text and "$ 500,00" in text
    plain = _sale(client, admin, db)
    client.post(f"/api/printing/sales/{plain['id']}/ticket", headers=admin, json={})
    assert "Envío" not in fake.jobs[-1][1].decode("cp858", errors="replace")


def test_ticket_voided_and_unknown_sale(seeded, db, fake):
    client, admin = seeded
    _configure(client, admin)
    sale = _sale(client, admin, db)
    client.post(f"/api/sales/{sale['id']}/void", headers=admin, json={"reason": "Error"})
    r = client.post(f"/api/printing/sales/{sale['id']}/ticket", headers=admin, json={"open_drawer": True})
    assert r.status_code == 200 and r.json()["drawer"] is False and b"ANULADO" in fake.jobs[-1][1]
    fake.jobs.clear()
    assert client.post("/api/printing/sales/999999/ticket", headers=admin, json={}).status_code == 404
    assert fake.jobs == []


def test_z_report_and_test_page(seeded, db, fake):
    client, admin = seeded
    _configure(client, admin)
    _sale(client, admin, db)
    sid = client.get("/api/cash/current", headers=admin).json()["id"]
    r = client.post(f"/api/printing/cash-sessions/{sid}/z", headers=admin)
    assert r.status_code == 200, r.text
    data = fake.jobs[-1][1]
    assert f"CIERRE DE CAJA (Z) · #{sid}".encode("cp858") in data and b"Arqueo por medio de pago" in data
    assert client.post("/api/printing/cash-sessions/99999/z", headers=admin).status_code == 404
    # Test page of an unsaved printer (admin only).
    r = client.post("/api/printing/test", headers=admin, json={"printer": _printer("Nueva", chars=32)})
    assert r.status_code == 200 and fake.jobs[-1][0] == "Nueva" and "áéíóú".encode("cp858") in fake.jobs[-1][1]
    cajero = login(client, "Caja Demo", "1111")
    assert client.post("/api/printing/test", headers=cajero, json={"printer": _printer()}).status_code == 403


def test_unavailable_outside_windows_and_in_demo(seeded, db, fake, monkeypatch):
    client, admin = seeded
    _configure(client, admin)
    sale = _sale(client, admin, db)
    monkeypatch.setattr(printers, "IS_WINDOWS", False)
    st = client.get("/api/printing/status", headers=admin).json()
    assert st["available"] is False and st["cashier"] is False and "solo en Windows" in st["reason"]
    assert client.post(f"/api/printing/sales/{sale['id']}/ticket", headers=admin, json={}).status_code == 409
    assert client.put("/api/printing/config", headers=admin, json={"printers": []}).status_code == 409
    assert client.get("/api/printing/windows-printers", headers=admin).json() == []
    monkeypatch.setattr(printers, "IS_WINDOWS", True)
    monkeypatch.setenv("BLOOM_DEMO", "1")
    st = client.get("/api/printing/status", headers=admin).json()
    assert st["available"] is False and "demo" in st["reason"]
    assert fake.jobs == []
    from app.demo.middleware import disabled_reason

    assert disabled_reason("POST", "/api/printing/test") and disabled_reason("PUT", "/api/printing/config")
    assert disabled_reason("GET", "/api/printing/status") is None


def _stations(db):
    cats = {c.name: c for c in db.scalars(select(ProductCategory))}
    barra = OrderStation(name="Barra", sort_order=1, print_tickets=False)
    cocina = OrderStation(name="Cocina", sort_order=2, print_tickets=True)
    db.add_all([barra, cocina])
    db.flush()
    for name in ("Cafetería", "Con leche"):
        cats[name].station_id = barra.id
    cats["Salado"].station_id = cocina.id
    db.commit()
    return barra.id, cocina.id


def test_kitchen_tickets_print_per_station_after_commit(seeded, db, fake):
    client, admin = seeded
    barra, cocina = _stations(db)
    cfg = _configure(client, admin, printers=[_printer(), _printer("Térmica cocina", target="192.168.0.51")])
    cfg = client.put("/api/printing/config", headers=admin, json={
        **cfg, "stations": {str(cocina): cfg["printers"][1]["id"], str(barra): cfg["printers"][0]["id"]}}).json()
    fake.jobs.clear()
    tostado = _pid(db, "Tostado de jamón y queso")
    r = client.post("/api/sales", headers=admin, json={
        "items": [{"product_id": _pid(db, "Latte")}, {"product_id": tostado, "notes": "Sin manteca"}],
        "payments": [{"method": "efectivo", "amount_cents": LATTE + 520000}]})
    assert r.status_code == 200, r.text
    # Only the kitchen prints (the bar has "Imprimir comanda" off), once, after the sale committed.
    assert [(n, d.split(" ")[0]) for n, _, d in fake.jobs] == [("Térmica cocina", "Comanda")]
    data = fake.jobs[0][1]
    assert "Tostado de jamón y queso".encode("cp858") in data and "» Sin manteca".encode("cp858") in data
    assert b"Latte" not in data and b"Cocina" in data
    board = client.get("/api/orders/board", params={"station_id": cocina}, headers=admin).json()
    assert {s["name"]: s["direct_print"] for s in board["stations"]} == {"Barra": True, "Cocina": True}
    assert board["print_failures"] == []

    # A sale that fails (rolled back) prints nothing.
    fake.jobs.clear()
    bad = client.post("/api/sales", headers=admin, json={"items": [{"product_id": tostado}],
                                                        "payments": [{"method": "efectivo", "amount_cents": 1}]})
    assert bad.status_code == 400 and fake.jobs == []

    # Printer down: the sale still goes through and the station's screen gets the failure to print it itself.
    fake.fail = "La impresora 192.168.0.51:9100 no respondió."
    r = client.post("/api/sales", headers=admin, json={"items": [{"product_id": tostado}],
                                                      "payments": [{"method": "efectivo", "amount_cents": 520000}]})
    assert r.status_code == 200
    board = client.get("/api/orders/board", params={"station_id": cocina}, headers=admin).json()
    new_id = next(o["id"] for o in board["orders"] if o["sale_id"] == r.json()["id"])
    assert board["print_failures"] == [{"order_id": new_id, "error": fake.fail}]
    other = client.get("/api/orders/board", params={"station_id": barra}, headers=admin).json()
    assert other["print_failures"] == []


def test_kitchen_tickets_without_printer_keep_the_screen_printing(seeded, db, fake):
    client, admin = seeded
    _barra, cocina = _stations(db)
    _configure(client, admin)  # cashier printer only
    fake.jobs.clear()
    _sale(client, admin, db, product="Tostado de jamón y queso", total=520000)
    assert fake.jobs == []
    board = client.get("/api/orders/board", params={"station_id": cocina}, headers=admin).json()
    assert {s["name"]: s["direct_print"] for s in board["stations"]} == {"Barra": False, "Cocina": False}


def test_reprinting_a_comanda_works_without_stations_and_needs_a_printer(seeded, db, fake):
    client, admin = seeded
    sale = _sale(client, admin, db)
    board = client.get("/api/orders/board", headers=admin).json()["orders"]
    order = next(o for o in board if o["sale_id"] == sale["id"])
    # Nowhere to print: 409, so the screen prints it from the browser.
    assert client.post(f"/api/printing/orders/{order['id']}/comanda", headers=admin).status_code == 409
    _configure(client, admin)  # cashier printer only, no stations
    fake.jobs.clear()
    r = client.post(f"/api/printing/orders/{order['id']}/comanda", headers=admin)
    assert r.status_code == 200, r.text
    assert [(n, d.split(" ")[0]) for n, _, d in fake.jobs] == [("Caja", "Comanda")]
    assert b"Latte" in fake.jobs[0][1]
    assert client.post("/api/printing/orders/999999/comanda", headers=admin).status_code == 404
    assert client.post(f"/api/printing/orders/{order['id']}/comanda", headers=login(client, "Caja Demo", "1111")).status_code == 200


def test_raw_tcp_transport_against_a_local_socket():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    got = bytearray()

    def serve():
        conn, _ = srv.accept()
        with conn:
            while chunk := conn.recv(4096):
                got.extend(chunk)

    th = threading.Thread(target=serve)
    th.start()
    printers.send_tcp("127.0.0.1", port, b"\x1b@hola\n" * 500)
    th.join(5)
    srv.close()
    assert bytes(got) == b"\x1b@hola\n" * 500
    with pytest.raises(PrintError, match=r"127.0.0.1"):  # refused or timed out (Windows retries)
        printers.send_tcp("127.0.0.1", port, b"x", timeout=1)


@pytest.mark.skipif(not printers.IS_WINDOWS, reason="Windows spooler")
def test_windows_printer_list_and_unknown_printer():
    rows = printers.list_windows_printers()
    assert isinstance(rows, list) and all(set(r) == {"name", "default"} for r in rows)
    with pytest.raises(PrintError, match="No se encontró la impresora"):
        printers.send_windows("Impresora que no existe 123", b"x")
