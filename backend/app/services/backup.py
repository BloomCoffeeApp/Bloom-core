import sqlite3
from datetime import datetime
from pathlib import Path

from app.config import BACKUP_DIR, DB_PATH


def create_backup(label: str = "manual") -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
    dest = BACKUP_DIR / f"cafeteria-{stamp}-{label}.db"
    n = 1
    while dest.exists():  # same second + same label (e.g. two restores in a row): never overwrite a copy
        n += 1
        dest = BACKUP_DIR / f"cafeteria-{stamp}-{n}-{label}.db"
    src = sqlite3.connect(DB_PATH)
    try:
        dst = sqlite3.connect(dest)
        with dst:
            src.backup(dst)
        dst.close()
    finally:
        src.close()
    return dest


def list_backups() -> list[Path]:
    return sorted(BACKUP_DIR.glob("cafeteria-*.db"), reverse=True)


def prune(keep: int) -> None:
    for old in list_backups()[keep:]:
        old.unlink(missing_ok=True)


def daily_backup_if_needed(keep: int = 30) -> Path | None:
    if not DB_PATH.exists():
        return None
    today = f"cafeteria-{datetime.now():%Y%m%d}"
    if any(p.name.startswith(today) and p.name.endswith("-auto.db") for p in list_backups()):
        return None
    path = create_backup("auto")
    prune(keep)
    return path


def backup_before_migration() -> Path | None:
    if DB_PATH.exists() and DB_PATH.stat().st_size > 0:
        path = create_backup("pre-migracion")
        prune(40)
        return path
    return None
