from datetime import timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Alert, CashSession, Customer, StockItem, utcnow
from app.services import alerts_engine
from app.services.stock import apply_movement
from app.services.timeutil import local_today
from tests.conftest import login


def _evaluate():
    with SessionLocal() as db:
        alerts_engine.evaluate(db)
        db.commit()


def _alerts(key_prefix):
    with SessionLocal() as db:
        return [
            (a.dedupe_key, a.status, a.severity)
            for a in db.scalars(select(Alert).where(Alert.dedupe_key.like(f"{key_prefix}%")).order_by(Alert.id))
        ]


def test_stock_alert_dedupe_and_autoresolve(seeded):
    client, h = seeded
    with SessionLocal() as db:
        item = StockItem(name="Leche test", unit="ml", min_qty=1000, current_qty=5000)
        db.add(item)
        db.commit()
        iid = item.id

    _evaluate()
    assert _alerts(f"stock_low:{iid}") == []

    with SessionLocal() as db:
        apply_movement(db, iid, -4500, "adjustment", reason="test")
        db.commit()
    _evaluate()
    _evaluate()  # idempotent: no duplicates
    assert _alerts(f"stock_low:{iid}") == [(f"stock_low:{iid}", "open", "warning")]

    # Goes to zero: low resolves, out opens (critical)
    with SessionLocal() as db:
        apply_movement(db, iid, -500, "adjustment", reason="test")
        db.commit()
    _evaluate()
    low = _alerts(f"stock_low:{iid}")
    assert len(low) == 1 and low[0][1] == "resolved"
    assert _alerts(f"stock_out:{iid}") == [(f"stock_out:{iid}", "open", "critical")]
    summary = client.get("/api/alerts/summary", headers=h).json()
    assert summary["critical"] >= 1

    # Restock: everything resolves
    with SessionLocal() as db:
        apply_movement(db, iid, 10000, "purchase", unit_cost_cents=1, reason="test")
        db.commit()
    _evaluate()
    assert all(s == "resolved" for _, s, _ in _alerts(f"stock_out:{iid}"))

    # Drops again later -> a brand-new alert is raised
    with SessionLocal() as db:
        apply_movement(db, iid, -9500, "adjustment", reason="test")
        db.commit()
    _evaluate()
    statuses = [s for _, s, _ in _alerts(f"stock_low:{iid}")]
    assert statuses.count("open") == 1 and statuses.count("resolved") == 1


def test_manual_resolve_sticks_and_read_endpoints(seeded):
    client, h = seeded
    with SessionLocal() as db:
        item = StockItem(name="Vasos test", unit="u", min_qty=100, current_qty=10)
        db.add(item)
        db.commit()
        iid = item.id
    r = client.post("/api/alerts/refresh", headers=h)
    assert r.status_code == 200 and r.json()["open"] >= 1
    alerts = client.get("/api/alerts", params={"status": "open"}, headers=h).json()
    a = next(x for x in alerts if x["entity"] == "stock_item" and x["entity_id"] == iid)
    assert a["link"] == "/stock"

    assert client.post(f"/api/alerts/{a['id']}/read", headers=h).json()["status"] == "read"
    assert client.post(f"/api/alerts/{a['id']}/resolve", headers=h).json()["status"] == "resolved"
    client.post("/api/alerts/refresh", headers=h)
    # still low, but the user dismissed it: no reopen, no duplicate
    assert _alerts(f"stock_low:{iid}") == [(f"stock_low:{iid}", "resolved", "warning")]

    barista = login(client, "Barista Demo", "2222")
    assert client.get("/api/alerts/summary", headers=barista).status_code == 200
    r = client.post("/api/alerts/read-all", headers=barista)
    assert r.status_code == 200 and r.json()["open"] == 0


def test_cash_open_from_yesterday(seeded):
    _client, _h = seeded
    with SessionLocal() as db:
        s = CashSession(opened_by=1, opened_at=utcnow() - timedelta(days=1, hours=1), opening_cents=0)
        db.add(s)
        db.commit()
        sid = s.id
    _evaluate()
    assert _alerts(f"cash_stale:{sid}") == [(f"cash_stale:{sid}", "open", "critical")]
    with SessionLocal() as db:
        s = db.get(CashSession, sid)
        s.status, s.closed_at = "closed", utcnow()
        db.commit()
    _evaluate()
    assert _alerts(f"cash_stale:{sid}")[0][1] == "resolved"


def test_birthday_alert_and_debt_over_limit(seeded):
    _client, _h = seeded
    today = local_today()
    with SessionLocal() as db:
        c = Customer(name="Cumpleañero", birthday=today.replace(year=1990), balance_cents=20000, credit_limit_cents=10000)
        db.add(c)
        db.commit()
        cid = c.id
    _evaluate()
    bday = _alerts(f"birthday:{cid}:")
    assert bday == [(f"birthday:{cid}:{today.isoformat()}", "open", "info")]
    assert _alerts(f"debt_over_limit:{cid}") == [(f"debt_over_limit:{cid}", "open", "warning")]
    with SessionLocal() as db:
        db.get(Customer, cid).balance_cents = 5000
        db.commit()
    _evaluate()
    assert _alerts(f"debt_over_limit:{cid}")[0][1] == "resolved"


def test_notices_crud_and_expiry(seeded):
    client, h = seeded
    cajero = login(client, "Caja Demo", "1111")
    assert client.post("/api/notices", json={"title": "x"}, headers=cajero).status_code == 403
    past = (utcnow() - timedelta(hours=1)).isoformat()
    r1 = client.post("/api/notices", json={"title": "Viejo", "expires_at": past}, headers=h)
    r2 = client.post("/api/notices", json={"title": "Llega el lechero", "pinned": True, "color": "sky"}, headers=h)
    r3 = client.post("/api/notices", json={"title": "Normal"}, headers=h)
    assert r1.status_code == r2.status_code == r3.status_code == 200
    titles = [n["title"] for n in client.get("/api/notices", headers=cajero).json()]
    assert "Viejo" not in titles
    assert titles.index("Llega el lechero") < titles.index("Normal")
    nid = r3.json()["id"]
    assert client.patch(f"/api/notices/{nid}", json={"body": "edit"}, headers=h).json()["body"] == "edit"
    assert client.delete(f"/api/notices/{nid}", headers=h).status_code == 200


def test_checklist_run_today(seeded):
    client, h = seeded
    barista = login(client, "Barista Demo", "2222")
    today = client.get("/api/checklists/today", headers=barista).json()
    opening = next(c for c in today if c["kind"] == "opening")
    assert opening["run_id"] is None and opening["total"] == 5

    run = client.post(f"/api/checklists/{opening['checklist_id']}/runs", headers=barista).json()
    again = client.post(f"/api/checklists/{opening['checklist_id']}/runs", headers=barista).json()
    assert run["run_id"] == again["run_id"]

    for i, it in enumerate(run["items"]):
        r = client.patch(f"/api/checklist-runs/{run['run_id']}/items/{it['item_id']}", json={"done": True}, headers=barista)
        assert r.status_code == 200
        body = r.json()
        assert body["items"][i]["done_by_name"] == "Barista Demo" and body["items"][i]["done_at"]
        assert (body["completed_at"] is not None) == (i == len(run["items"]) - 1)

    first = run["items"][0]["item_id"]
    r = client.patch(f"/api/checklist-runs/{run['run_id']}/items/{first}", json={"done": False}, headers=barista).json()
    assert r["completed_at"] is None and r["done"] == 4

    # Manager admin of checklists
    assert client.post("/api/checklists", json={"name": "X"}, headers=barista).status_code == 403
    r = client.post("/api/checklists", json={"name": "Mitad del día", "items": [{"text": "Reponer servilletas"}]}, headers=h)
    assert r.status_code == 200 and len(r.json()["items"]) == 1
    cid = r.json()["id"]
    item_id = r.json()["items"][0]["id"]
    r = client.patch(f"/api/checklists/{cid}", json={"items": [{"id": item_id, "text": "Reponer servilletas y sorbetes"}, {"text": "Limpiar mesas"}]}, headers=h)
    assert [i["text"] for i in r.json()["items"]] == ["Reponer servilletas y sorbetes", "Limpiar mesas"]
    assert r.json()["items"][0]["id"] == item_id
