"""Stable, anonymous id of this computer (a license is bound to it)."""

import hashlib
import os
import platform
import sys
import uuid
from functools import lru_cache

from app.config import APP_ID


def _raw_id() -> str:
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            ) as key:
                return str(winreg.QueryValueEx(key, "MachineGuid")[0])
        except OSError:
            pass
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            with open(path, encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            pass
    return f"{platform.node()}-{uuid.getnode()}"


@lru_cache
def machine_id() -> str:
    """Hashed with the app id: it never exposes the real hardware id."""
    override = os.environ.get("BLOOM_MACHINE_ID")  # tests / support
    raw = override or _raw_id()
    return hashlib.sha256(f"{APP_ID}:{raw}".encode()).hexdigest()[:32]


def machine_name() -> str:
    return platform.node()[:60] or "PC"
