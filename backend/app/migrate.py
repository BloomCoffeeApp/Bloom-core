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


def latest_healthy_backup(exclude: Path | None = None) -> Path | None:
    """The newest backup that passes SQLite's check (newest first; a damaged copy is skipped)."""
    from app.services.backup import list_backups

    for candidate in list_backups():
        if exclude is not None and candidate == exclude:
            continue
        if is_healthy(candidate):
            return candidate
    return None


def _recover(reason: str, fresh: Path | None) -> Path:
    """Replaces a damaged database with the best healthy copy: the one just taken (it reads through
    the WAL, so it can be fine when the main file isn't) or else the newest healthy backup."""
    candidates = [c for c in (fresh,) if c is not None and is_healthy(c)]
    copy = candidates[0] if candidates else latest_healthy_backup(exclude=fresh)
    if copy is None:
        raise DatabaseDamaged(f"La base de datos {DB_PATH} está dañada y no hay una copia de seguridad sana.")
    log.warning("Damaged database (%s): restored the backup %s", reason, copy.name)
    _replace_with(copy)
    global last_recovery
    last_recovery = {"backup": copy.name, "reason": reason, "at": datetime.now().isoformat(timespec="seconds")}
    return copy


last_recovery: dict | None = None  # set when this start had to restore a backup (shown by /api/system/info)


def describe_files() -> str:
    """Sizes of the database files, for the log (helps trace a damaged database)."""
    db = Path(DB_PATH)
    parts = []
    for suffix in ("", "-wal", "-shm"):
        f = Path(f"{db}{suffix}")
        parts.append(f"{f.name}={f.stat().st_size if f.exists() else '-'}")
    return " ".join(parts)


def upgrade_db() -> None:
    """Check, backup, migrate. The health check runs FIRST: a damaged database can make the backup itself
    fail, and then nothing else would run. A damaged database is replaced by the consistent copy just taken
    (the backup API reads through the WAL, so it can be healthy when the main file isn't) or, if that copy
    can't be taken or is damaged too, by the newest healthy backup. A migration that fails halfway is rolled
    back to the pre-migration copy instead of leaving a half-migrated database. Nothing is ever deleted."""
    from app.services.backup import backup_before_migration

    db = Path(DB_PATH)
    log.info("Starting with %s", describe_files())
    healthy = not db.exists() or db.stat().st_size == 0 or is_healthy(db)
    try:
        backup = backup_before_migration()
    except sqlite3.DatabaseError as e:
        log.warning("Pre-migration backup failed: %s", e)
        backup = None
        healthy = False
    if not healthy or (backup is not None and not is_healthy(db)):
        backup = _recover("startup check", backup)
    try:
        command.upgrade(alembic_config(), "head")
    except Exception:
        if backup is not None and is_healthy(backup):
            log.exception("Migration failed: restoring the pre-migration copy %s", backup.name)
            _replace_with(backup)
        raise
