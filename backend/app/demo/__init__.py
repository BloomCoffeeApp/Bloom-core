"""Online demo mode: every visitor gets a throwaway copy of a demo database.

Off unless the server is started with `BLOOM_DEMO=1`, and **always off in the desktop build**
(`config.FROZEN`): the packaged app can't be switched into it by an environment variable.

How it works (see `sandboxes.py` and `middleware.py`):
- At startup a template database is built once (migrations + the regular demo seed).
- The first page load without a valid cookie copies the template to `<sandbox dir>/<sid>.db`,
  where `sid` is a random 128-bit hex id; the cookie holds only that id (HttpOnly, SameSite=Lax,
  Secure over https). Nothing else about the visitor is stored.
- Each request uses its own sandbox (`get_db` is overridden), so visitors never see each other's data.
- Idle sandboxes are deleted after `BLOOM_DEMO_IDLE_HOURS`; at most `BLOOM_DEMO_MAX_SANDBOXES` exist.
- Every Pro feature is on, and everything that would reach outside the sandbox (license server,
  account linking, updates, backups/restore, LAN mode, photo uploads) answers a friendly 403.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from app import config

if TYPE_CHECKING:
    from fastapi import FastAPI


def is_enabled() -> bool:
    """Demo mode is requested AND this is not the packaged desktop app."""
    return os.environ.get("BLOOM_DEMO") == "1" and not config.FROZEN


def _int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.environ.get(name, default)))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, default))
    except ValueError:
        return default
    return value if value > 0 else default


@dataclass(frozen=True)
class DemoSettings:
    root: Path
    idle_hours: float = 2.0
    max_sandboxes: int = 30
    new_per_ip_per_hour: int = 10
    requests_per_minute: int = 300
    # Proxies in front of the server that append to X-Forwarded-For (0 = trust no header).
    # Render alone: 1. Cloudflare Worker -> Render: 2.
    proxy_hops: int = 0
    # Shared with the Cloudflare Worker: only requests carrying it may use all `proxy_hops`; anything
    # that reached the server another way (e.g. the public onrender.com URL) trusts one hop at most.
    proxy_secret: str = ""
    site_url: str = ""
    cleanup_every_s: int = 60
    users: tuple[dict, ...] = field(default_factory=tuple)

    @property
    def idle_seconds(self) -> float:
        return self.idle_hours * 3600

    @classmethod
    def from_env(cls) -> DemoSettings:
        return cls(
            root=Path(os.environ.get("BLOOM_DEMO_DIR") or (config.DATA_DIR / "demo-sandboxes")),
            idle_hours=_float("BLOOM_DEMO_IDLE_HOURS", 2.0),
            max_sandboxes=_int("BLOOM_DEMO_MAX_SANDBOXES", 30),
            new_per_ip_per_hour=_int("BLOOM_DEMO_NEW_PER_IP_HOUR", 10),
            requests_per_minute=_int("BLOOM_DEMO_REQUESTS_PER_MIN", 300),
            proxy_hops=_int("BLOOM_DEMO_PROXY_HOPS", 0, minimum=0),
            proxy_secret=os.environ.get("BLOOM_DEMO_PROXY_SECRET", "").strip(),
            site_url=os.environ.get("BLOOM_DEMO_SITE_URL", "").strip(),
            cleanup_every_s=_int("BLOOM_DEMO_CLEANUP_EVERY_S", 60),
            users=DEMO_USERS,
        )


# Who the visitor can log in as (all fictional; PINs are shown in the demo banner).
DEMO_BUSINESS = "Café Demo"
DEMO_ADMIN = {"name": "Dueño Demo", "pin": "1234", "role": "Dueño"}
DEMO_USERS: tuple[dict, ...] = (
    DEMO_ADMIN,
    {"name": "Caja Demo", "pin": "1111", "role": "Caja"},
    {"name": "Barista Demo", "pin": "2222", "role": "Barista"},
    {"name": "Encargado Demo", "pin": "3333", "role": "Encargado"},
)

_manager = None  # SandboxManager while demo mode is installed


def manager():
    return _manager


def public_info(request=None) -> dict | None:
    """What the frontend needs for the banner (`/api/health` → `demo`)."""
    if _manager is None:
        return None
    s = _manager.settings
    state = getattr(request, "state", None)
    return {
        "session": bool(getattr(state, "demo_session", False)),
        "start_url": "/api/demo/new",
        "idle_hours": s.idle_hours,
        "site_url": s.site_url or None,
        "users": [{"name": u["name"], "pin": u["pin"], "role": u["role"]} for u in s.users],
    }


def install(app: FastAPI, settings: DemoSettings | None = None) -> None:
    """Wires demo mode into the app (called by `create_app` only when `is_enabled()`)."""
    global _manager
    from app.auth import login_throttle
    from app.db import get_db
    from app.demo.middleware import DemoMiddleware, current_sandbox_id
    from app.demo.sandboxes import SandboxManager, get_sandbox_db

    _manager = SandboxManager(settings or DemoSettings.from_env())
    app.dependency_overrides[get_db] = get_sandbox_db
    # PIN lockouts are per sandbox: user ids repeat in every copy of the template.
    login_throttle.namespace = lambda: current_sandbox_id.get() or ""
    app.add_middleware(DemoMiddleware, manager=_manager)


def uninstall() -> None:
    """Tests only."""
    global _manager
    from app.auth import login_throttle

    if _manager is not None:
        _manager.shutdown(delete_all=True)
    _manager = None
    login_throttle.namespace = None


def demo_license_status():
    """Synthetic license: everything Pro is on in the demo (never reaches the license server)."""
    from app.licensing.status import LicenseStatus

    return LicenseStatus(plan="pro", valid=True, features=["*"], customer="Demo online", perpetual=True, machine_id="demo")
