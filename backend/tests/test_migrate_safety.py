"""Startup migration safety: a damaged database recovers from the copy taken just before migrating,
and a migration that fails halfway is rolled back to that copy (nothing is ever deleted)."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from app import migrate
from app.services import backup as backup_svc


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    db = tmp_path / "data.db"
    with closing(sqlite3.connect(db)) as con:
        con.execute("CREATE TABLE t (v TEXT)")
        con.execute("INSERT INTO t VALUES ('original')")
        con.commit()
    monkeypatch.setattr(migrate, "DB_PATH", db)
    monkeypatch.setattr(backup_svc, "DB_PATH", db)
    monkeypatch.setattr(backup_svc, "BACKUP_DIR", tmp_path / "backups")
    return db


def _value(db: Path) -> str:
    with closing(sqlite3.connect(db)) as con:
        return con.execute("SELECT v FROM t").fetchone()[0]


def test_healthy_database_just_migrates(isolated_db, monkeypatch):
    calls = []
    monkeypatch.setattr(migrate.command, "upgrade", lambda cfg, rev: calls.append(rev))
    migrate.upgrade_db()
    assert calls == ["head"] and _value(isolated_db) == "original"
    assert not list(isolated_db.parent.glob("*.danada-*"))


def test_damaged_database_recovers_from_the_fresh_copy(isolated_db, monkeypatch):
    real = migrate.is_healthy
    checked: list[Path] = []

    def fake(p):
        if Path(p) == isolated_db and not checked:
            checked.append(Path(p))
            return False  # the main file looks damaged the first time
        return real(p)

    monkeypatch.setattr(migrate, "is_healthy", fake)
    monkeypatch.setattr(migrate.command, "upgrade", lambda cfg, rev: None)
    migrate.upgrade_db()
    assert checked
    assert len(list(isolated_db.parent.glob("data.db.danada-*"))) == 1  # kept aside, not deleted
    assert _value(isolated_db) == "original"


def test_both_damaged_stops_without_touching_anything(isolated_db, monkeypatch):
    monkeypatch.setattr(migrate, "is_healthy", lambda p: False)
    with pytest.raises(migrate.DatabaseDamaged):
        migrate.upgrade_db()
    assert not list(isolated_db.parent.glob("data.db.danada-*")) and _value(isolated_db) == "original"


def test_failed_migration_rolls_back_to_the_copy(isolated_db, monkeypatch):
    def half_migration(cfg, rev):
        with closing(sqlite3.connect(isolated_db)) as con:
            con.execute("UPDATE t SET v = 'half-migrated'")
            con.commit()
        raise RuntimeError("boom")

    monkeypatch.setattr(migrate.command, "upgrade", half_migration)
    with pytest.raises(RuntimeError, match="boom"):
        migrate.upgrade_db()
    assert _value(isolated_db) == "original"
    assert len(list(isolated_db.parent.glob("data.db.danada-*"))) == 1


def test_is_healthy_detects_a_corrupt_file(tmp_path):
    bad = tmp_path / "bad.db"
    bad.write_bytes(b"SQLite format 3\x00" + b"\xff" * 4096)
    assert not migrate.is_healthy(bad)
