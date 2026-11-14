"""Support diagnostic: the small, readable summary the owner can send to support by hand.

What it holds: app version, system, database health and size, last backup, printer, active modules, license
plan, hours running and the last errors of `app.log`. What it NEVER holds: sales, customers, products, prices,
names or e-mails. The shape mirrors the closed schema of the license server (`POST /v1/diagnostics`, module
`license_server/diagnostics.py` of the private repo), which scrubs everything again on arrival.

`build()` is what the preview shows and what `send()` sends: the same function, so the owner sees exactly
what leaves the computer.
"""

import logging
import platform
import re
import sqlite3
import time
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app import config
from app.licensing import client as license_client
from app.licensing.status import current_status
from app.services import backup as backup_svc
from app.services import business_profile, printing

log = logging.getLogger("cafeteria.diagnostics")

MAX_ERRORS = 20
ERROR_WINDOW = timedelta(hours=24)
LOG_TAIL_BYTES = 512 * 1024
_STARTED = time.monotonic()

# ---------------------------------------------------------------- scrubbing (same rules as the server)

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_WIN_USER = re.compile(r"(?i)([A-Z]:[\\/]+Users[\\/]+)[^\\/\s\"']+")
_POSIX_USER = re.compile(r"(/(?:home|Users)/)[^/\s\"']+")
_LONG_SECRET = re.compile(r"\b[A-Za-z0-9_\-]{32,}\b")
_BEARER = re.compile(r"(?i)(bearer|token|key|secret|password|authorization)(\s*[=:]\s*|\s+)[^\s,;\"']{6,}")


def scrub(value: Any, limit: int = 300) -> str:
    """Text safe to send: no e-mails, no user names inside paths, no bearer-like values or long tokens."""
    s = "" if value is None else str(value)
    s = _EMAIL.sub("[email]", s)
    s = _WIN_USER.sub(r"\1[usuario]", s)
    s = _POSIX_USER.sub(r"\1[usuario]", s)
    s = _BEARER.sub(lambda m: f"{m.group(1)}{m.group(2)}[oculto]", s)
    s = _LONG_SECRET.sub("[oculto]", s)
    s = " ".join(s.split())
    return s[:limit]


# ---------------------------------------------------------------- pieces


def _db_health() -> tuple[bool | None, float | None]:
    db_path = Path(config.DB_PATH)
    size = sum(p.stat().st_size for p in (db_path, Path(f"{db_path}-wal")) if p.exists())
    try:
        with closing(sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=5)) as con:
            row = con.execute("PRAGMA quick_check").fetchone()
        ok: bool | None = bool(row and row[0] == "ok")
    except sqlite3.Error:
        ok = False
    return ok, round(size / (1024 * 1024), 2)


def _backups() -> tuple[str | None, int]:
    files = backup_svc.list_backups()
    if not files:
        return None, 0
    newest = max(files, key=lambda p: p.stat().st_mtime)
    when = datetime.fromtimestamp(newest.stat().st_mtime, UTC)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ"), len(files)


def _printer(db: Session) -> dict[str, Any]:
    cfg = printing.get_cfg(db)
    return {"configured": bool(cfg["printers"]) and cfg["cashier_printer"] is not None, "last_ok": printing.last_print_ok()}


def _license() -> dict[str, Any]:
    st = current_status()
    if st.valid:
        state = "grace" if st.in_grace else "active"
    elif st.problem:
        state = "invalid"
    else:
        state = "none"
    expires = None
    if st.expires_at:
        expires = datetime.fromtimestamp(st.expires_at, UTC).strftime("%Y-%m-%d")
    return {"state": state, "plan": st.plan_key or st.plan, "expires": expires}


_LOG_LINE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ (ERROR|CRITICAL) ([\w.\-]+): (.*)$")


def recent_errors(log_path: Path | None = None, now: datetime | None = None) -> list[dict[str, str]]:
    """Last errors (ERROR/CRITICAL) of the last 24 h from app.log, newest last, scrubbed. Tracebacks are skipped:
    only the first line of each record, which is where the message is."""
    path = log_path or config.DATA_DIR / "app.log"
    now = now or datetime.now()
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - LOG_TAIL_BYTES))
            text = f.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    out: list[dict[str, str]] = []
    for line in text.splitlines():
        m = _LOG_LINE.match(line)
        if not m:
            continue
        try:
            ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        if now - ts > ERROR_WINDOW:
            continue
        out.append({"ts": m.group(1), "kind": scrub(m.group(3), 60), "message": scrub(m.group(4), 300)})
    return out[-MAX_ERRORS:]


# ---------------------------------------------------------------- the summary


def build(db: Session) -> dict[str, Any]:
    """The diagnostic exactly as it would be sent (matches the server's closed schema; nothing else is added)."""
    db_ok, size_mb = _db_health()
    last_backup_at, backups = _backups()
    modules = sorted(k for k, on in business_profile.effective(db).items() if on)
    return {
        "os": scrub(platform.platform(), 80),
        "app_version": scrub(config.APP_VERSION, 20),
        "db_ok": db_ok,
        "db_size_mb": size_mb,
        "last_backup_at": last_backup_at,
        "backups": backups,
        "printer": _printer(db),
        "license": _license(),
        "modules": [scrub(m, 40) for m in modules][:40],
        "errors": recent_errors(),
        "uptime_hours": round((time.monotonic() - _STARTED) / 3600, 1),
    }


def availability() -> tuple[bool, str | None]:
    if not license_client.server_url():
        return False, "Esta instalación no tiene un servidor de soporte configurado, así que no se puede enviar el diagnóstico."
    return True, None


def preview(db: Session) -> dict[str, Any]:
    ok, reason = availability()
    return {"available": ok, "reason": reason, "diagnostic": build(db), "includes_license": license_client.has_token()}


def send(db: Session) -> str:
    """Builds the diagnostic again and sends it; returns the support code. Raises LicenseServerError."""
    ok, reason = availability()
    if not ok:
        raise license_client.LicenseServerError(reason or "")
    resp = license_client.send_diagnostic(build(db))
    code = str(resp.get("support_code") or "")
    if not code:
        raise license_client.LicenseServerError("Respuesta inválida del servidor de soporte.")
    return code
