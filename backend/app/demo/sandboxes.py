"""Per-visitor SQLite sandboxes for the online demo: template, copies, caps and cleanup."""

from __future__ import annotations

import logging
import re
import secrets
import shutil
import sqlite3
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import HTTPException, Request
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.db import configure_sqlite
from app.demo import DEMO_ADMIN, DEMO_BUSINESS, DemoSettings

log = logging.getLogger("cafeteria.demo")

# 128 random bits as lowercase hex: the ONLY thing a cookie can name. Anything else is ignored,
# so a cookie can never point outside the sandbox folder.
SID_RE = re.compile(r"[0-9a-f]{32}")
TEMPLATE_NAME = "template.db"


class SandboxesFull(Exception):
    """The concurrent sandbox cap was reached."""


class TemplateNotReady(Exception):
    """The demo database is still being built (first seconds after startup)."""


def valid_sid(value: str | None) -> bool:
    return bool(value) and SID_RE.fullmatch(value) is not None  # type: ignore[arg-type]


def new_sid() -> str:
    return secrets.token_hex(16)


def _sqlite_engine(path: Path) -> Engine:
    # NullPool: no idle connections per sandbox (memory on small hosts, and files can be deleted).
    engine = create_engine(
        f"sqlite:///{path.as_posix()}", poolclass=NullPool, connect_args={"check_same_thread": False, "timeout": 30}
    )
    configure_sqlite(engine)
    return engine


def build_template(path: Path) -> None:
    """Fresh demo database at `path`: migrations + first-time setup with the regular demo seed."""
    from alembic import command

    from app.migrate import alembic_config
    from app.models import UserSession
    from app.routers.auth import setup
    from app.schemas.users import SetupIn
    from app.services import alerts_engine
    from app.services import settings as settings_svc

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".building")
    for p in (tmp, Path(f"{tmp}-wal"), Path(f"{tmp}-shm")):
        p.unlink(missing_ok=True)
    cfg = alembic_config()
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{tmp.as_posix()}")
    command.upgrade(cfg, "head")

    engine = _sqlite_engine(tmp)
    try:
        with Session(engine, autoflush=False, expire_on_commit=False) as db:
            # Same code path as the app's first-time setup screen ("load demo data").
            setup(SetupIn(business_name=DEMO_BUSINESS, admin_name=DEMO_ADMIN["name"], admin_pin=DEMO_ADMIN["pin"], load_demo=True), db)
            db.query(UserSession).delete()  # no login token may be shared by every copy
            biz = settings_svc.get(db, "business")
            settings_svc.put(db, "business", {**biz, "name": DEMO_BUSINESS, "ticket_footer": "Demo de Bloom: datos de ejemplo"})
            settings_svc.put(db, "backup", {"enabled": False, "keep": 1})
            alerts_engine.evaluate(db)
            db.commit()
    finally:
        engine.dispose()
    # One self-contained file (no -wal/-shm) so copies are a plain file copy.
    con = sqlite3.connect(tmp)
    try:
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        con.execute("PRAGMA journal_mode=DELETE")
        con.execute("VACUUM")
    finally:
        con.close()
    tmp.replace(path)


def _remove_db_files(path: Path) -> None:
    for p in (path, Path(f"{path}-wal"), Path(f"{path}-shm"), Path(f"{path}-journal")):
        try:
            p.unlink(missing_ok=True)
        except OSError:
            log.warning("could not delete %s", p)


@dataclass
class Sandbox:
    sid: str
    path: Path
    engine: Engine
    factory: sessionmaker
    created: float
    last_seen: float
    active: int = 0  # requests in flight (never deleted while > 0)


@dataclass
class _Window:
    start: float = 0.0
    count: int = 0


@dataclass
class SandboxManager:
    settings: DemoSettings
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _boxes: dict[str, Sandbox] = field(default_factory=dict)
    _template: Path | None = None
    _new_by_ip: dict[str, list[float]] = field(default_factory=dict)
    _req_windows: dict[str, _Window] = field(default_factory=dict)
    _stop: threading.Event = field(default_factory=threading.Event)
    _threads: list[threading.Thread] = field(default_factory=list)

    @property
    def root(self) -> Path:
        return self.settings.root

    @property
    def sandbox_dir(self) -> Path:
        return self.root / "sandboxes"

    # ------------------------------------------------------------------ lifecycle

    def start(self, *, background: bool = True) -> None:
        """Wipes leftovers of a previous run, builds the template (~3 s; the demo data is dated
        relative to today) and starts the cleanup loop. Until the template exists, visitors get a
        "Preparando la demo…" page that reloads itself."""
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        for leftover in self.sandbox_dir.iterdir():
            if leftover.is_file():
                _remove_db_files(leftover)
        self._stop.clear()
        if background:
            self._spawn(self._build_fresh_template, "demo-template")
            self._spawn(self._cleanup_loop, "demo-cleanup")
        else:
            self._build_fresh_template()

    def _spawn(self, target, name: str) -> None:
        t = threading.Thread(target=target, name=name, daemon=True)
        t.start()
        self._threads.append(t)

    def use_template(self, path: Path) -> None:
        """Serves copies of an already built template (tests)."""
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        self._template = path

    def _build_fresh_template(self) -> None:
        target = self.root / TEMPLATE_NAME
        started = time.monotonic()
        try:
            build_template(target)
        except Exception:
            log.exception("demo template build failed")
            return
        self._template = target
        log.info("demo template ready in %.1f s", time.monotonic() - started)

    def shutdown(self, *, delete_all: bool = False) -> None:
        self._stop.set()
        if delete_all:
            with self._lock:
                boxes, self._boxes = list(self._boxes.values()), {}
            for box in boxes:
                box.engine.dispose()
                _remove_db_files(box.path)

    @property
    def template_ready(self) -> bool:
        return self._template is not None and self._template.is_file()

    # ------------------------------------------------------------------ sandboxes

    def count(self) -> int:
        with self._lock:
            return len(self._boxes)

    def peek(self, sid: str | None) -> bool:
        """Whether `sid` names a live sandbox (without counting as activity)."""
        if not valid_sid(sid):
            return False
        with self._lock:
            return sid in self._boxes

    def get(self, sid: str | None) -> Sandbox | None:
        if not valid_sid(sid):
            return None
        with self._lock:
            box = self._boxes.get(sid)  # type: ignore[arg-type]
            if box is not None:
                box.last_seen = time.time()
            return box

    def create(self) -> Sandbox:
        """New sandbox copied from the template. Raises SandboxesFull / TemplateNotReady."""
        if not self.template_ready:
            raise TemplateNotReady
        sid = new_sid()
        path = self.sandbox_dir / f"{sid}.db"
        with self._lock:
            if len(self._boxes) >= self.settings.max_sandboxes:
                raise SandboxesFull
            now = time.time()
            # Reserve the slot before the (slow) copy so concurrent creations respect the cap.
            engine = _sqlite_engine(path)
            box = Sandbox(sid, path, engine, sessionmaker(bind=engine, autoflush=False, expire_on_commit=False), now, now, active=1)
            self._boxes[sid] = box
        try:
            shutil.copyfile(self._template, path)  # type: ignore[arg-type]
        except Exception:
            with self._lock:
                self._boxes.pop(sid, None)
            engine.dispose()
            _remove_db_files(path)
            raise
        with self._lock:
            box.active -= 1
        return box

    def acquire(self, box: Sandbox) -> None:
        with self._lock:
            box.active += 1
            box.last_seen = time.time()

    def release(self, box: Sandbox) -> None:
        with self._lock:
            box.active = max(0, box.active - 1)
            box.last_seen = time.time()

    def cleanup(self, now: float | None = None) -> int:
        """Deletes sandboxes idle for longer than the limit (and stray files). Returns how many."""
        now = time.time() if now is None else now
        limit = self.settings.idle_seconds
        with self._lock:
            expired = [b for b in self._boxes.values() if b.active == 0 and now - b.last_seen > limit]
            for b in expired:
                del self._boxes[b.sid]
            known = {b.path.name for b in self._boxes.values()}
            # Forget rate-limit windows that no longer matter.
            hour_ago = now - 3600
            self._new_by_ip = {ip: [t for t in ts if t > hour_ago] for ip, ts in self._new_by_ip.items() if any(t > hour_ago for t in ts)}
            self._req_windows = {k: w for k, w in self._req_windows.items() if now - w.start < 120}
        for b in expired:
            b.engine.dispose()
            _remove_db_files(b.path)
        if self.sandbox_dir.is_dir():
            for f in self.sandbox_dir.glob("*.db"):
                if f.name not in known and now - f.stat().st_mtime > 300:
                    _remove_db_files(f)
        if expired:
            log.info("demo: deleted %d idle sandbox(es), %d left", len(expired), len(known))
        return len(expired)

    def _cleanup_loop(self) -> None:
        while not self._stop.wait(self.settings.cleanup_every_s):
            try:
                self.cleanup()
            except Exception:
                log.exception("demo cleanup failed")

    # ------------------------------------------------------------------ rate limits

    def allow_new(self, ip: str, now: float | None = None) -> bool:
        """At most `new_per_ip_per_hour` sandboxes per client IP per rolling hour."""
        now = time.time() if now is None else now
        with self._lock:
            recent = [t for t in self._new_by_ip.get(ip, []) if now - t < 3600]
            if len(recent) >= self.settings.new_per_ip_per_hour:
                self._new_by_ip[ip] = recent
                return False
            recent.append(now)
            self._new_by_ip[ip] = recent
            return True

    def allow_request(self, key: str, now: float | None = None) -> bool:
        """Fixed one-minute window of `requests_per_minute` per key (client IP)."""
        now = time.time() if now is None else now
        with self._lock:
            w = self._req_windows.setdefault(key, _Window(now, 0))
            if now - w.start >= 60:
                w.start, w.count = now, 0
            w.count += 1
            return w.count <= self.settings.requests_per_minute


def get_sandbox_db(request: Request) -> Iterator[Session]:
    """Replaces `app.db.get_db` in demo mode: the session of THIS visitor's sandbox, never a shared DB."""
    box: Sandbox | None = getattr(request.state, "demo_sandbox", None)
    if box is None:
        raise HTTPException(503, "La demo se está preparando. Recargá la página en unos segundos.")
    db = box.factory()
    try:
        yield db
    finally:
        db.close()
