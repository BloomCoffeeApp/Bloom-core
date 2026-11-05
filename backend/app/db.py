from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event
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
