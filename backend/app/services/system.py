"""System info, backups/restore, LAN helpers and audit log listing."""

import io
import ipaddress
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import qrcode
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config, lan
from app.db import engine
from app.models import AuditLog, User
from app.services import backup as backup_svc
from app.services import settings as settings_svc


def _backup_label(name: str) -> str:
    # cafeteria-YYYYmmdd-HHMMSS-<label>.db
    stem = name.removesuffix(".db")
    parts = stem.split("-", 3)
    return parts[3] if len(parts) == 4 else "manual"


def backup_info(p: Path) -> dict[str, Any]:
    st = p.stat()
    return {
        "name": p.name,
        "size_bytes": st.st_size,
        "created_at": datetime.fromtimestamp(st.st_mtime, UTC).replace(tzinfo=None),
        "label": _backup_label(p.name),
    }


def list_backups() -> list[dict[str, Any]]:
    return [backup_info(p) for p in backup_svc.list_backups()]


def resolve_backup(name: str) -> Path | None:
    """Returns the backup path only if `name` is exactly one of the listed backups (no path traversal)."""
    for p in backup_svc.list_backups():
        if p.name == name:
            return p
    return None


def create_backup(db: Session, label: str = "manual") -> dict[str, Any]:
    path = backup_svc.create_backup(label)
    keep = (settings_svc.get(db, "backup") or {}).get("keep", 30)
    backup_svc.prune(max(int(keep), 1) + 10)  # manual backups are generous; daily job prunes too
    return backup_info(path)


def _validate_sqlite(path: Path) -> None:
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        ok = con.execute("PRAGMA quick_check").fetchone()
        if not ok or ok[0] != "ok":
            raise ValueError("El respaldo está dañado")
        has_users = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
        if not has_users:
            raise ValueError("El archivo no parece un respaldo de la app")
    except sqlite3.DatabaseError as e:
        raise ValueError("El archivo no es una base de datos válida") from e
    finally:
        con.close()


def restore_backup(path: Path) -> str:
    """Creates a 'pre-restore' safety backup and copies `path` over the live DB with the SQLite backup API.

    Returns the safety backup file name. The app should be restarted afterwards.
    """
    _validate_sqlite(path)
    safety = backup_svc.create_backup("pre-restore")
    engine.dispose()  # drop pooled connections so they don't keep stale pages/schema
    src = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(config.DB_PATH, timeout=30)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    engine.dispose()
    return safety.name


def lan_ips() -> list[str]:
    ips: list[str] = []
    try:  # primary outbound interface (no packet is actually sent for UDP connect)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            ips.append(s.getsockname()[0])
        finally:
            s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = str(info[4][0])
            if ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    return [ip for ip in ips if not ip.startswith(("127.", "169.254.", "0."))]


_profile_cache: dict[str, tuple[float, str | None]] = {}


def network_category(ip: str) -> str | None:
    """Windows' category of the network `ip` is on ("Public", "Private", "DomainAuthenticated").

    Windows blocks incoming connections on Public networks: phones can't open the app or the menu.
    """
    if sys.platform != "win32":
        return None
    ip = str(ipaddress.IPv4Address(ip))  # it goes into a command line
    now = time.monotonic()
    hit = _profile_cache.get(ip)
    if hit and now - hit[0] < 30:
        return hit[1]
    cmd = f"(Get-NetConnectionProfile -InterfaceIndex (Get-NetIPAddress -IPAddress '{ip}' -ErrorAction Stop).InterfaceIndex).NetworkCategory"
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True, text=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        out = ""
    category = out.splitlines()[0].strip() if out else None
    _profile_cache[ip] = (now, category)
    return category


def lan_url() -> str | None:
    ips = lan_ips()
    return f"http://{ips[0]}:{config.PORT}" if ips else None


def menu_url() -> str | None:
    base = lan_url()
    return f"{base}/menu" if base else None


def info(db: Session) -> dict[str, Any]:
    db_path = Path(config.DB_PATH)
    size = sum(p.stat().st_size for p in (db_path, Path(f"{db_path}-wal")) if p.exists())
    backups = list_backups()
    ips = lan_ips()
    lan_enabled = bool((settings_svc.get(db, "network") or {}).get("lan_enabled"))
    return {
        "app_name": config.APP_NAME,
        "version": config.APP_VERSION,
        "data_dir": str(config.DATA_DIR),
        "db_path": str(db_path),
        "db_size_bytes": size,
        "backups_count": len(backups),
        "last_backup": backups[0] if backups else None,
        "lan_ips": ips,
        "lan_url": f"http://{ips[0]}:{config.PORT}" if ips else None,
        "port": config.PORT,
        "lan_enabled": lan_enabled,
        "lan_active": lan.active(lan_enabled),
        "network_public": bool(ips) and network_category(ips[0]) == "Public",
    }


def qr_png(text: str) -> bytes:
    qr = qrcode.QRCode(border=2, box_size=10)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image()
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue()


def audit_rows(db: Session, limit: int) -> list[dict[str, Any]]:
    rows = db.execute(
        select(AuditLog, User.name).outerjoin(User, User.id == AuditLog.user_id)
        .order_by(AuditLog.ts.desc(), AuditLog.id.desc()).limit(limit)
    ).all()
    return [
        {
            "id": a.id, "ts": a.ts, "user_id": a.user_id, "user_name": name, "action": a.action,
            "entity": a.entity, "entity_id": a.entity_id, "payload": a.payload,
        }
        for a, name in rows
    ]
