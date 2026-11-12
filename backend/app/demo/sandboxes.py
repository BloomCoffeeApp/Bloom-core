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
DEMO_MARKER = "demo_sandbox"  # settings key present only in demo databases
ENDED_KEEP_S = 24 * 3600  # how long we remember why a sandbox ended (for the end screen)


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
            # Marks every copy as demo data: restoring a backup made from it is refused (system.restore_backup).
            settings_svc.put(db, DEMO_MARKER, True)
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
    _blocked: dict[str, float] = field(default_factory=dict)  # ip -> blocked until
    _ended: dict[str, tuple[str, float]] = field(default_factory=dict)  # sid -> (reason, when)
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

    def _expired(self, box: Sandbox, now: float) -> bool:
        return now - box.created >= self.settings.lifetime_seconds

    def peek(self, sid: str | None, now: float | None = None) -> bool:
        """Whether `sid` names a live sandbox (without counting as activity)."""
        return self.expires_in(sid, now) is not None

    def expires_in(self, sid: str | None, now: float | None = None) -> int | None:
        """Seconds left of the sandbox's absolute lifetime; None if there's no live sandbox."""
        if not valid_sid(sid):
            return None
        now = time.time() if now is None else now
        with self._lock:
            box = self._boxes.get(sid)  # type: ignore[arg-type]
            if box is None or self._expired(box, now):
                return None
            return max(0, int(box.created + self.settings.lifetime_seconds - now))

    def ended_reason(self, sid: str | None) -> str | None:
        """"lifetime" | "idle" for a sandbox this server deleted (or expired) recently."""
        if not valid_sid(sid):
            return None
        now = time.time()
        with self._lock:
            box = self._boxes.get(sid)  # type: ignore[arg-type]
            if box is not None and self._expired(box, now):
                return "lifetime"
            ended = self._ended.get(sid)  # type: ignore[arg-type]
            return ended[0] if ended else None

    def get(self, sid: str | None, now: float | None = None) -> Sandbox | None:
        """The live sandbox. Past its absolute lifetime it's gone for the visitor at once (deleted by the
        next cleanup, never while a request is using it)."""
        if not valid_sid(sid):
            return None
        now = time.time() if now is None else now
        with self._lock:
            box = self._boxes.get(sid)  # type: ignore[arg-type]
            if box is None or self._expired(box, now):
                return None
            box.last_seen = now
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
            expired = []
            for b in list(self._boxes.values()):
                if b.active:
                    continue
                if self._expired(b, now):
                    expired.append(b)
                    self._ended[b.sid] = ("lifetime", now)
                elif now - b.last_seen > limit:
                    expired.append(b)
                    self._ended[b.sid] = ("idle", now)
            for b in expired:
                del self._boxes[b.sid]
            self._ended = {k: v for k, v in self._ended.items() if now - v[1] < ENDED_KEEP_S}
            self._blocked = {ip: until for ip, until in self._blocked.items() if until > now}
            known = {b.path.name for b in self._boxes.values()}
            # Forget rate-limit windows that no longer matter.
            day_ago = now - 86400
            self._new_by_ip = {ip: [t for t in ts if t > day_ago] for ip, ts in self._new_by_ip.items() if any(t > day_ago for t in ts)}
            self._req_windows = {k: w for k, w in self._req_windows.items() if now - w.start < 120}
        for b in expired:
            b.engine.dispose()
            _remove_db_files(b.path)
        if self.sandbox_dir.is_dir():
            for f in self.sandbox_dir.glob("*.db"):
                if f.name not in known and now - f.stat().st_mtime > 300:
                    _remove_db_files(f)
        if expired:
            log.info("demo: deleted %d idle/expired sandbox(es), %d left", len(expired), len(known))
        return len(expired)

    def _cleanup_loop(self) -> None:
        while not self._stop.wait(self.settings.cleanup_every_s):
            try:
                self.cleanup()
            except Exception:
                log.exception("demo cleanup failed")

    # ------------------------------------------------------------------ rate limits

    def allow_new(self, ip: str, now: float | None = None) -> bool:
        """check_new + record_new in one step (tests and simple callers)."""
        if self.check_new(ip, now) is not None:
            return False
        self.record_new(ip, now)
        return True

    def check_new(self, ip: str, now: float | None = None) -> str | None:
        """None if `ip` may get a new sandbox (call `record_new` once it exists), or why not: "blocked"
        (temporary block after a burst), "burst" (this attempt started the block), "day" (rolling 24 h cap)
        or "hour" (rolling hour cap)."""
        now = time.time() if now is None else now
        s = self.settings
        with self._lock:
            if self._blocked.get(ip, 0) > now:
                return "blocked"
            recent = [t for t in self._new_by_ip.get(ip, []) if now - t < 86400]
            self._new_by_ip[ip] = recent
            if sum(1 for t in recent if now - t < s.burst_minutes * 60) >= s.burst_count:
                self._blocked[ip] = now + s.block_minutes * 60
                log.warning("demo: %s blocked for %g min (sandboxes in a burst)", ip, s.block_minutes)
                return "burst"
            if len(recent) >= s.new_per_ip_per_day:
                return "day"
            if sum(1 for t in recent if now - t < 3600) >= s.new_per_ip_per_hour:
                return "hour"
            return None

    def record_new(self, ip: str, now: float | None = None) -> None:
        now = time.time() if now is None else now
        with self._lock:
            self._new_by_ip.setdefault(ip, []).append(now)

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
