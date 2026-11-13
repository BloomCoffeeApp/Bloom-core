"""Backup and restore end to end: restoring really brings the data back (not just a 200), the pre-restore safety
copy lets you undo it, and a broken or foreign file never touches the live database."""
import sqlite3
from contextlib import closing

from sqlalchemy import func, select

from app.config import DB_PATH
from app.db import SessionLocal, engine
from app.models import Product, Sale
from app.services import backup as backup_svc


def _sale(client, admin, qty=1):
    with SessionLocal() as s:
        pid, price = (lambda p: (p.id, p.price_cents))(s.scalar(select(Product).where(Product.name == "Latte")))
    r = client.post("/api/sales", json={"items": [{"product_id": pid, "qty": qty}], "channel": "salon",
                                        "payments": [{"method": "debito", "amount_cents": qty * price}]}, headers=admin)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _sale_ids() -> set[int]:
    with SessionLocal() as s:
        return set(s.scalars(select(Sale.id)))


def _reopen():
    engine.dispose()  # what a restart does: drop pooled connections to the replaced file


def test_restore_brings_back_exactly_the_data_of_that_backup_and_can_be_undone(seeded):
    client, admin = seeded
    first = _sale(client, admin)
    name = client.post("/api/system/backups", headers=admin).json()["name"]
    ids_at_backup = _sale_ids()
    second = _sale(client, admin, qty=2)
    assert second in _sale_ids()

    r = client.post("/api/system/restore", json={"name": name}, headers=admin)
    assert r.status_code == 200, r.text
    safety = r.json()["safety_backup"]
    _reopen()

    assert _sale_ids() == ids_at_backup, "restoring must bring back exactly the data of that backup"
    assert first in _sale_ids() and second not in _sale_ids()

    # The safety copy taken right before restoring still has the later sale: restoring it undoes the restore.
    r = client.post("/api/system/restore", json={"name": safety}, headers=admin)
    assert r.status_code == 200, r.text
    _reopen()
    assert second in _sale_ids()


def test_restored_database_is_healthy_and_keeps_working(seeded):
    client, admin = seeded
    name = client.post("/api/system/backups", headers=admin).json()["name"]
    _sale(client, admin)
    assert client.post("/api/system/restore", json={"name": name}, headers=admin).status_code == 200
    _reopen()
    with closing(sqlite3.connect(DB_PATH)) as con:
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    # Selling again after a restore must keep ticket numbers unique (no reused number).
    a, b = _sale(client, admin), _sale(client, admin)
    with SessionLocal() as s:
        numbers = list(s.scalars(select(Sale.number).where(Sale.id.in_([a, b]))))
        assert len(set(numbers)) == 2
        assert s.scalar(select(func.count(Sale.id))) == len(_sale_ids())


def test_a_corrupt_backup_is_refused_and_the_live_database_is_untouched(seeded):
    client, admin = seeded
    name = client.post("/api/system/backups", headers=admin).json()["name"]
    victim = next(p for p in backup_svc.list_backups() if p.name == name)
    victim.write_bytes(b"this is not a sqlite database" * 50)  # damaged file in the backups folder
    before = _sale_ids()
    r = client.post("/api/system/restore", json={"name": name}, headers=admin)
    assert r.status_code == 400, r.text
    _reopen()
    assert _sale_ids() == before
    with closing(sqlite3.connect(DB_PATH)) as con:
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_two_backups_in_the_same_second_never_overwrite_each_other(seeded):
    client, admin = seeded
    a = client.post("/api/system/backups", headers=admin).json()["name"]
    b = client.post("/api/system/backups", headers=admin).json()["name"]
    c = client.post("/api/system/backups", headers=admin).json()["name"]
    assert len({a, b, c}) == 3
    names = {p.name for p in backup_svc.list_backups()}
    assert {a, b, c} <= names
