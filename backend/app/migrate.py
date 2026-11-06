import logging
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import DATABASE_URL, DB_PATH, MIGRATIONS_DIR

log = logging.getLogger("cafeteria.migrate")


class DatabaseDamaged(RuntimeError):
    pass


def alembic_config() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    return cfg


def is_healthy(path: Path) -> bool:
    """SQLite's own structural check (read-only)."""
    try:
        with closing(sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True, timeout=5)) as con:
            return con.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    except sqlite3.DatabaseError:
        return False


def _replace_with(backup: Path) -> None:
    """Puts `backup` in place of the database; the current files are kept aside, never deleted."""
    from app.db import engine

    engine.dispose()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    db = Path(DB_PATH)
    for suffix in ("", "-wal", "-shm"):
        f = Path(f"{db}{suffix}")
        if f.exists():
            f.rename(f"{db}.danada-{stamp}{suffix}")
    shutil.copy2(backup, db)


def upgrade_db() -> None:
    """Backup, check, migrate. A damaged database is replaced by the consistent copy just taken (the
    backup API reads through the WAL, so it can be healthy when the main file isn't), and a migration
    that fails halfway is rolled back to that copy instead of leaving a half-migrated database."""
    from app.services.backup import backup_before_migration

    backup = backup_before_migration()
    if backup is not None and not is_healthy(Path(DB_PATH)):
        if not is_healthy(backup):
            raise DatabaseDamaged(f"La base de datos {DB_PATH} está dañada y la copia de seguridad también.")
        log.warning("Damaged database: restored the copy taken just before migrating (%s)", backup.name)
        _replace_with(backup)
    try:
        command.upgrade(alembic_config(), "head")
    except Exception:
        if backup is not None and is_healthy(backup):
            log.exception("Migration failed: restoring the pre-migration copy %s", backup.name)
            _replace_with(backup)
        raise
