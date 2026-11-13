from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import DATABASE_URL

def _sqlite_pragmas(dbapi_conn, _record):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.close()


def configure_sqlite(target: Engine) -> Engine:
    """Applies the app's SQLite pragmas to every new connection of `target` (also the demo sandboxes)."""
    event.listen(target, "connect", _sqlite_pragmas)
    return target


engine = configure_sqlite(create_engine(DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 30}))


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def like_contains(column, term: str):
    """`column` contains `term`, case-insensitive, with `%`, `_` and backslash in the term taken LITERALLY.

    The value is always a bound parameter (no SQL injection), but unescaped `%` / `_` act as wildcards: searching
    for "100%" or "a_b" would match far more than typed. Use this for every user-typed search box."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return column.ilike(f"%{escaped}%", escape="\\")


def lock_writes(db: Session) -> None:
    """Takes SQLite's write lock NOW (waits up to the engine timeout if another request is writing).

    Use it before reading a value you are about to turn into a new row (`max(number) + 1`): without it two
    requests read the same maximum and the second one fails on the unique constraint. The statement matches no
    row, but any write statement starts the write transaction, which lasts until commit/rollback."""
    db.execute(text("UPDATE settings SET value = value WHERE 0"))
