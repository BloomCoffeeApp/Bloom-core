"""Gestión de gastos: expenses, monthly fixed expenses, paying from the cash drawer, alerts and the result."""

from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.models import CashMovement, Expense, RecurringExpense
from app.services import expenses as svc
from app.services.timeutil import local_today
from tests.conftest import login


def _cat(client, h, name="Alquiler") -> int:
    cats = client.get("/api/expenses/categories", headers=h).json()
    return next(c["id"] for c in cats if c["name"] == name)


def _close_cash(client, h):
    if client.get("/api/cash/current", headers=h).json():
        assert client.post("/api/cash/close", json={"counts": []}, headers=h).status_code == 200


def _open_cash(client, h, opening=1_000_00):
    _close_cash(client, h)
    r = client.post("/api/cash/open", json={"opening_cents": opening}, headers=h)
    assert r.status_code == 200, r.text


@pytest.fixture()
def h(seeded):
    client, headers = seeded
    return client, headers


def test_default_categories_and_editing(h):
    client, hh = h
    cats = client.get("/api/expenses/categories", headers=hh).json()
    names = {c["name"] for c in cats}
    assert {"Alquiler", "Sueldos y cargas sociales", "Impuestos y tasas", "Otros"} <= names
    r = client.post("/api/expenses/categories", json={"name": "Seguros", "kind": "fixed"}, headers=hh)
    assert r.status_code == 200
    assert client.post("/api/expenses/categories", json={"name": "seguros"}, headers=hh).status_code == 409
    cid = r.json()["id"]
    assert client.patch(f"/api/expenses/categories/{cid}", json={"active": False}, headers=hh).json()["active"] is False
    # Archived categories can't take new expenses.
    r = client.post("/api/expenses", json={"category_id": cid, "description": "x", "amount_cents": 100}, headers=hh)
    assert r.status_code == 400


def test_variable_expense_crud_in_cents(h):
    client, hh = h
    cid = _cat(client, hh, "Mantenimiento y reparaciones")
    r = client.post("/api/expenses", json={"category_id": cid, "description": "Arreglo de la heladera", "amount_cents": 3_500_050,
                                           "payment_method": "transferencia", "notes": "Técnico del barrio"}, headers=hh)
    assert r.status_code == 200, r.text
    e = r.json()
    assert e["status"] == "paid" and e["kind"] == "variable" and e["amount_cents"] == 3_500_050
    assert e["date"] == local_today().isoformat() and e["paid_at"] and not e["from_cash"]
    month = client.get("/api/expenses", headers=hh).json()
    assert any(i["id"] == e["id"] for i in month["items"])
    r = client.patch(f"/api/expenses/{e['id']}", json={"amount_cents": 3_600_000, "notes": ""}, headers=hh)
    assert r.json()["amount_cents"] == 3_600_000 and r.json()["notes"] is None
    assert client.delete(f"/api/expenses/{e['id']}", headers=hh).status_code == 200
    assert client.patch(f"/api/expenses/{e['id']}", json={"amount_cents": 1}, headers=hh).status_code == 404


def test_unknown_payment_method_is_rejected(h):
    client, hh = h
    r = client.post("/api/expenses", json={"category_id": _cat(client, hh), "description": "x", "amount_cents": 100,
                                           "payment_method": "bitcoin"}, headers=hh)
    assert r.status_code == 400


def test_cash_expense_creates_an_egreso_in_the_same_transaction(h):
    client, hh = h
    cid = _cat(client, hh, "Limpieza y descartables")
    body = {"category_id": cid, "description": "Lavandina", "amount_cents": 250_000, "from_cash": True}
    # Without an open drawer nothing is saved (no expense, no movement).
    _close_cash(client, hh)
    before = client.get("/api/expenses", headers=hh).json()["totals"]["count"]
    r = client.post("/api/expenses", json=body, headers=hh)
    assert r.status_code == 409 and "caja abierta" in r.json()["detail"]
    assert client.get("/api/expenses", headers=hh).json()["totals"]["count"] == before

    _open_cash(client, hh, 1_000_000)
    r = client.post("/api/expenses", json=body, headers=hh)
    assert r.status_code == 200, r.text
    e = r.json()
    assert e["from_cash"] and e["payment_method"] == "efectivo"
    cur = client.get("/api/cash/current", headers=hh).json()
    out = [m for m in cur["movements"] if m["type"] == "out"]
    assert len(out) == 1 and out[0]["amount_cents"] == 250_000 and out[0]["reason"] == "Gasto: Lavandina"
    assert cur["expected_cash_cents"] == 1_000_000 - 250_000

    # Editing the amount while the drawer is open updates the egreso; switching to another method removes it.
    client.patch(f"/api/expenses/{e['id']}", json={"amount_cents": 300_000}, headers=hh)
    assert client.get("/api/cash/current", headers=hh).json()["expected_cash_cents"] == 700_000
    r = client.patch(f"/api/expenses/{e['id']}", json={"payment_method": "debito"}, headers=hh)
    assert r.json()["from_cash"] is False
    assert client.get("/api/cash/current", headers=hh).json()["expected_cash_cents"] == 1_000_000


def test_cash_expense_of_a_closed_drawer_is_locked(h, db):
    client, hh = h
    _open_cash(client, hh, 500_000)
    e = client.post("/api/expenses", json={"category_id": _cat(client, hh, "Otros"), "description": "Propina flete",
                                           "amount_cents": 100_000, "from_cash": True}, headers=hh).json()
    # Deleting while the drawer is open removes the egreso too.
    assert client.delete(f"/api/expenses/{e['id']}", headers=hh).status_code == 200
    assert client.get("/api/cash/current", headers=hh).json()["expected_cash_cents"] == 500_000
    e = client.post("/api/expenses", json={"category_id": _cat(client, hh, "Otros"), "description": "Hielo",
                                           "amount_cents": 100_000, "from_cash": True}, headers=hh).json()
    r = client.post("/api/cash/close", json={"counts": [{"payment_method": "efectivo", "counted_cents": 400_000}]}, headers=hh)
    assert r.status_code == 200, r.text
    assert client.delete(f"/api/expenses/{e['id']}", headers=hh).status_code == 409
    assert client.patch(f"/api/expenses/{e['id']}", json={"amount_cents": 1}, headers=hh).status_code == 409
    # Fields that don't touch the money are still editable.
    assert client.patch(f"/api/expenses/{e['id']}", json={"description": "Hielo (bolsas)"}, headers=hh).status_code == 200
    mv = db.get(CashMovement, db.scalar(select(Expense.cash_movement_id).where(Expense.id == e["id"])))
    assert mv.reason == "Gasto: Hielo (bolsas)"


def test_pending_then_pay_from_cash(h):
    client, hh = h
    due = local_today() + timedelta(days=2)
    r = client.post("/api/expenses", json={"category_id": _cat(client, hh), "description": "Expensas", "amount_cents": 8_000_000,
                                           "status": "pending", "due_date": due.isoformat()}, headers=hh)
    e = r.json()
    assert e["status"] == "pending" and e["due_date"] == due.isoformat() and e["paid_at"] is None
    assert client.post("/api/expenses", json={"category_id": _cat(client, hh), "description": "x", "amount_cents": 1,
                                              "status": "pending", "from_cash": True}, headers=hh).status_code == 400
    _open_cash(client, hh, 10_000_000)
    r = client.post(f"/api/expenses/{e['id']}/pay", json={"from_cash": True, "amount_cents": 8_100_000}, headers=hh)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "paid" and r.json()["amount_cents"] == 8_100_000 and r.json()["from_cash"]
    assert client.get("/api/cash/current", headers=hh).json()["expected_cash_cents"] == 1_900_000
    assert client.post(f"/api/expenses/{e['id']}/pay", json={}, headers=hh).status_code == 409


def test_recurring_generates_one_pending_expense_per_month(db, seeded):
    client, hh = seeded
    today = local_today()
    cur = svc.period_of(today)
    r = client.post("/api/expenses/recurring", json={"category_id": _cat(client, hh), "description": "Alquiler depósito",
                                                     "amount_cents": 20_000_000, "day_of_month": 31,
                                                     "start_period": svc.add_months(cur, -2)}, headers=hh)
    assert r.status_code == 200, r.text
    rid = db.scalar(select(RecurringExpense.id).where(RecurringExpense.description == "Alquiler depósito"))
    rows = list(db.scalars(select(Expense).where(Expense.recurring_id == rid).order_by(Expense.period)))
    assert [e.period for e in rows] == [svc.add_months(cur, -2), svc.add_months(cur, -1), cur]
    assert all(e.status == "pending" and e.kind == "fixed" for e in rows)
    # Day 31 is clamped to each month's last day.
    for e in rows:
        assert e.due_date == svc.period_bounds(e.period)[1] and e.date == e.due_date
    # Idempotent; a month deleted by hand is not generated again.
    assert svc.generate_recurring(db) == 0
    client.delete(f"/api/expenses/{rows[0].id}", headers=hh)
    db.expire_all()
    assert svc.generate_recurring(db) == 0
    # Next month: exactly one more, with the template's current amount.
    client.patch(f"/api/expenses/recurring/{rid}", json={"amount_cents": 22_000_000}, headers=hh)
    nxt = svc.period_bounds(svc.add_months(cur, 1))[0] + timedelta(days=3)
    svc.generate_recurring(db, nxt)
    db.commit()
    assert db.scalar(select(func.count(Expense.id)).where(Expense.recurring_id == rid)) == 3
    new = db.scalar(select(Expense).where(Expense.recurring_id == rid, Expense.period == svc.add_months(cur, 1)))
    assert new.amount_cents == 22_000_000
    # Paused templates stop generating.
    client.patch(f"/api/expenses/recurring/{rid}", json={"active": False}, headers=hh)
    db.expire_all()
    svc.generate_recurring(db, nxt + timedelta(days=40))
    db.commit()
    assert db.scalar(select(func.count(Expense.id)).where(Expense.recurring_id == rid)) == 3
    listed = client.get("/api/expenses/recurring", headers=hh).json()
    assert any(r["id"] == rid and r["active"] is False for r in listed)


def test_several_requests_generating_the_same_month_at_once_make_it_once(db, seeded):
    """Opening Gastos on two screens (or the periodic job and a screen) at the same moment: one expense, no errors."""
    import threading

    from fastapi.testclient import TestClient

    from app.main import create_app

    client, hh = seeded
    cur = svc.period_of(local_today())
    r = client.post("/api/expenses/recurring", json={"category_id": _cat(client, hh), "description": "Internet", "amount_cents": 5_000_00,
                                                     "day_of_month": 10, "start_period": svc.add_months(cur, 1)}, headers=hh)
    assert r.status_code == 200, r.text
    rid = db.scalar(select(RecurringExpense.id).where(RecurringExpense.description == "Internet"))
    tpl = db.get(RecurringExpense, rid)
    tpl.start_period, tpl.last_period = cur, None  # as if this month still had to be generated
    db.commit()
    codes: list[int] = []
    lock = threading.Lock()

    def fire():
        c = TestClient(create_app(run_lifespan=False))
        h2 = login(c, "Admin", "0000")
        res = c.get("/api/expenses/summary", headers=h2)
        with lock:
            codes.append(res.status_code)

    threads = [threading.Thread(target=fire) for _ in range(8)]
    [t.start() for t in threads]
    [t.join(timeout=60) for t in threads]
    assert codes == [200] * 8, codes
    db.expire_all()
    assert db.scalar(select(func.count(Expense.id)).where(Expense.recurring_id == rid)) == 1


def test_period_helpers():
    assert svc.add_months("2026-12", 1) == "2027-01"
    assert svc.add_months("2026-01", -1) == "2025-12"
    assert svc.due_date_in("2027-02", 30) == date(2027, 2, 28)
    assert svc.period_bounds("2028-02") == (date(2028, 2, 1), date(2028, 2, 29))


def test_due_soon_expenses_raise_alerts(h):
    client, hh = h
    today = local_today()
    cid = _cat(client, hh)
    soon = client.post("/api/expenses", json={"category_id": cid, "description": "Luz del local", "amount_cents": 1_000_000,
                                              "status": "pending", "due_date": (today + timedelta(days=1)).isoformat()}, headers=hh).json()
    late = client.post("/api/expenses", json={"category_id": cid, "description": "ABL", "amount_cents": 500_000,
                                              "status": "pending", "due_date": (today - timedelta(days=2)).isoformat()}, headers=hh).json()
    far = client.post("/api/expenses", json={"category_id": cid, "description": "Seguro anual", "amount_cents": 500_000,
                                             "status": "pending", "due_date": (today + timedelta(days=20)).isoformat()}, headers=hh).json()
    client.post("/api/alerts/refresh", headers=hh)
    alerts = {a["entity_id"]: a for a in client.get("/api/alerts", headers=hh).json() if a["type"] == "expense_due"}
    assert alerts[soon["id"]]["severity"] == "warning" and "vence en 1 día" in alerts[soon["id"]]["title"]
    assert alerts[late["id"]]["severity"] == "critical" and alerts[late["id"]]["link"] == "/gastos"
    assert far["id"] not in alerts
    # Paying it resolves the alert.
    client.post(f"/api/expenses/{late['id']}/pay", json={"payment_method": "transferencia"}, headers=hh)
    client.post("/api/alerts/refresh", headers=hh)
    active = {a["entity_id"] for a in client.get("/api/alerts", headers=hh).json() if a["type"] == "expense_due"}
    assert late["id"] not in active and soon["id"] in active


def test_month_result_is_sales_minus_cogs_losses_and_expenses(h, db):
    client, hh = h
    period = svc.period_of(local_today())
    first = svc.period_bounds(period)[0]
    before = client.get("/api/expenses/summary", headers=hh).json()
    cur = before["current"]
    assert cur["profit_cents"] == cur["sales_cents"] - cur["cogs_cents"] - cur["losses_cents"] - cur["expenses_cents"]
    assert cur["losses_cents"] == cur["waste_cents"] + cur["courtesy_cost_cents"]
    assert before["previous"]["period"] == svc.add_months(period, -1)
    client.post("/api/expenses", json={"category_id": _cat(client, hh), "description": "Extra", "amount_cents": 1_234_567,
                                       "date": first.isoformat()}, headers=hh)
    after = client.get("/api/expenses/summary", headers=hh).json()["current"]
    assert after["expenses_cents"] == cur["expenses_cents"] + 1_234_567
    assert after["profit_cents"] == cur["profit_cents"] - 1_234_567
    # An expense dated in the previous month doesn't touch this month.
    prev_first = svc.period_bounds(svc.add_months(period, -1))[0]
    client.post("/api/expenses", json={"category_id": _cat(client, hh), "description": "Viejo", "amount_cents": 1000,
                                       "date": prev_first.isoformat()}, headers=hh)
    assert client.get("/api/expenses/summary", headers=hh).json()["current"]["expenses_cents"] == after["expenses_cents"]


def test_month_result_counts_waste_and_courtesies(db, seeded):
    client, hh = seeded
    today = local_today()
    res = svc.result(db, today - timedelta(days=60), today)
    assert res["courtesy_cost_cents"] >= 0 and res["waste_cents"] >= 0
    assert res["profit_cents"] == res["gross_margin_cents"] - res["losses_cents"] - res["expenses_cents"]


def test_demo_data_has_expenses(db, seeded):
    today = local_today()
    rows = list(db.scalars(select(Expense)))
    assert rows, "the demo seed loads fictional expenses"
    assert all(e.status == "paid" for e in rows if e.due_date and e.due_date < today)
    assert any(e.recurring_id for e in rows)


def test_receipt_photo_is_private_and_reencoded(h, tmp_path):
    import io

    from PIL import Image

    client, hh = h
    e = client.post("/api/expenses", json={"category_id": _cat(client, hh), "description": "Con foto", "amount_cents": 100},
                    headers=hh).json()
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(buf, "JPEG")
    r = client.put(f"/api/expenses/{e['id']}/receipt", content=buf.getvalue(), headers={**hh, "Content-Type": "image/jpeg"})
    assert r.status_code == 200, r.text
    assert r.json()["has_receipt"] is True
    got = client.get(f"/api/expenses/{e['id']}/receipt", headers=hh)
    assert got.status_code == 200 and got.headers["content-type"] == "image/webp"
    assert client.get(f"/api/expenses/{e['id']}/receipt").status_code == 401
    bad = client.put(f"/api/expenses/{e['id']}/receipt", content=b"not an image", headers={**hh, "Content-Type": "image/png"})
    assert bad.status_code == 415
    assert client.delete(f"/api/expenses/{e['id']}/receipt", headers=hh).json()["has_receipt"] is False
    assert client.get(f"/api/expenses/{e['id']}/receipt", headers=hh).status_code == 404


def test_cashier_cannot_see_expenses(h):
    client, _ = h
    ch = login(client, "Caja Demo", "1111")
    assert client.get("/api/expenses", headers=ch).status_code == 403
    assert client.get("/api/expenses/summary", headers=ch).status_code == 403


def test_expense_alerts_are_hidden_from_cashiers(h):
    client, hh = h
    due = (local_today() + timedelta(days=1)).isoformat()
    client.post("/api/expenses", json={"category_id": _cat(client, hh, "Sueldos y cargas sociales"), "description": "Sueldo Ana",
                                       "amount_cents": 90_000_000, "status": "pending", "due_date": due}, headers=hh)
    client.post("/api/alerts/refresh", headers=hh)
    assert any(a["type"] == "expense_due" for a in client.get("/api/alerts", headers=hh).json())
    ch = login(client, "Caja Demo", "1111")
    assert not any(a["type"] == "expense_due" for a in client.get("/api/alerts", headers=ch).json())
