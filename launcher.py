"""Desktop entry point: runs the local API server in a thread and opens a native window.

Dev:       backend/.venv/Scripts/python launcher.py   (after `npm run build` in frontend/)
Packaged:  <exeName>.exe from brand.json (see build/build.ps1)
"""

import json
import logging
import os
import socket
import sqlite3
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.config import APP_DISPLAY_NAME, APP_ID, DATA_DIR, DB_PATH, PORT  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    filename=DATA_DIR / "app.log",
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("cafeteria.launcher")


def lan_enabled() -> bool:
    """Reads the 'network' setting straight from SQLite (before the app is up)."""
    if not DB_PATH.exists():
        return False
    try:
        with sqlite3.connect(DB_PATH) as con:
            row = con.execute("SELECT value FROM settings WHERE key='network'").fetchone()
        enabled = bool(row and json.loads(row[0]).get("lan_enabled"))
    except Exception:
        return False
    # Listening on the network is a Pro feature; a lapsed license falls back to this PC only.
    from app.licensing import has_feature

    return enabled and has_feature("lan")


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def is_our_server(port: int) -> bool:
    """True only if the process on `port` answers /api/health with our app id."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1.5) as r:
            return json.loads(r.read()).get("app") == APP_ID
    except Exception:
        return False


def pick_port() -> tuple[int, bool]:
    """Returns (port, already_running). Skips ports taken by other local apps."""
    for port in range(PORT, PORT + 20):
        if not port_in_use(port):
            return port, False
        if is_our_server(port):
            return port, True
        log.warning("Port %s is used by another application, trying the next one", port)
    raise RuntimeError("No free port found")


def run_server(host: str, port: int) -> None:
    # Runs in a thread of a windowed .exe: without this, a startup error would vanish silently.
    try:
        import uvicorn

        from app.main import app

        uvicorn.run(app, host=host, port=port, log_level="warning", log_config=None)
    except BaseException:
        log.exception("The local server crashed")
        raise


def wait_ready(port: int, timeout: float = 30) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_our_server(port):
            return True
        time.sleep(0.2)
    return False


def main() -> None:
    import webview

    from app import config

    port, running = pick_port()
    config.PORT = port  # so LAN URL / QR show the real port
    if running:
        log.info("%s already running on %s; opening a window only", APP_DISPLAY_NAME, port)
    else:
        host = "0.0.0.0" if lan_enabled() else "127.0.0.1"
        threading.Thread(target=run_server, args=(host, port), daemon=True).start()
    if not wait_ready(port):
        log.error("Server did not start in time")
    from desktop_window import WindowApi

    # Frameless: the UI draws its own title bar (drag, minimize, maximize, close).
    min_size = (1024, 680)
    api = WindowApi(DATA_DIR / "window.json", min_size)
    window = webview.create_window(
        APP_DISPLAY_NAME,
        f"http://127.0.0.1:{port}",
        **api._initial_geometry(1400, 900),
        min_size=min_size,
        text_select=True,
        frameless=True,
        easy_drag=False,
        shadow=True,
        js_api=api,
    )
    api._attach(window)
    webview.start(private_mode=False, storage_path=str(DATA_DIR / "webview"))
    os._exit(0)


if __name__ == "__main__":
    main()
