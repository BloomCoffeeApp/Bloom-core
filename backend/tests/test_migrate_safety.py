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
    monkeypatch.setattr(migrate, "last_recovery", None)
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


def _healthy_copy(isolated_db: Path, name: str, value: str) -> Path:
    backups = isolated_db.parent / "backups"
    backups.mkdir(exist_ok=True)
    dest = backups / name
    with closing(sqlite3.connect(dest)) as con:
        con.execute("CREATE TABLE t (v TEXT)")
        con.execute("INSERT INTO t VALUES (?)", (value,))
        con.commit()
    return dest


def test_backup_failing_on_a_damaged_database_recovers_from_the_newest_healthy_backup(isolated_db, monkeypatch):
    """15/11: a damaged database made the pre-migration backup raise before any check, so the server died
    («127.0.0.1 rechazó la conexión») instead of recovering."""
    _healthy_copy(isolated_db, "cafeteria-20261101-100000-auto.db", "older")
    _healthy_copy(isolated_db, "cafeteria-20261102-100000-auto.db", "newest")
    isolated_db.write_bytes(b"SQLite format 3\x00" + b"\xff" * 4096)  # damaged main file

    def failing_backup():
        raise sqlite3.DatabaseError("database disk image is malformed")

    monkeypatch.setattr(backup_svc, "backup_before_migration", failing_backup)
    monkeypatch.setattr(migrate.command, "upgrade", lambda cfg, rev: None)
    migrate.upgrade_db()
    assert _value(isolated_db) == "newest"
    assert len(list(isolated_db.parent.glob("data.db.danada-*"))) == 1  # the damaged file is kept aside
    assert migrate.last_recovery and migrate.last_recovery["backup"] == "cafeteria-20261102-100000-auto.db"


def test_damaged_backups_are_skipped(isolated_db, monkeypatch):
    _healthy_copy(isolated_db, "cafeteria-20261101-100000-auto.db", "good")
    bad = isolated_db.parent / "backups" / "cafeteria-20261102-100000-auto.db"
    bad.write_bytes(b"SQLite format 3\x00" + b"\xff" * 4096)
    assert migrate.latest_healthy_backup().name == "cafeteria-20261101-100000-auto.db"


def test_no_healthy_copy_anywhere_stops_without_touching_anything(isolated_db, monkeypatch):
    isolated_db.write_bytes(b"SQLite format 3\x00" + b"\xff" * 4096)

    def failing_backup():
        raise sqlite3.DatabaseError("database disk image is malformed")

    monkeypatch.setattr(backup_svc, "backup_before_migration", failing_backup)
    with pytest.raises(migrate.DatabaseDamaged):
        migrate.upgrade_db()
    assert not list(isolated_db.parent.glob("data.db.danada-*"))


def test_close_cleanly_folds_the_wal_into_the_main_file(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, text

    from app import db as db_mod

    path = tmp_path / "wal.db"
    engine = db_mod.configure_sqlite(create_engine(f"sqlite:///{path.as_posix()}"))
    with engine.begin() as con:
        con.execute(text("CREATE TABLE t (v TEXT)"))
        con.execute(text("INSERT INTO t VALUES ('x')"))
    wal = Path(f"{path}-wal")
    assert wal.exists() and wal.stat().st_size > 0
    monkeypatch.setattr(db_mod, "engine", engine)
    db_mod.close_cleanly()
    assert not wal.exists() or wal.stat().st_size == 0
    assert migrate.is_healthy(path)
