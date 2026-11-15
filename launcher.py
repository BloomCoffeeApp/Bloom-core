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
from contextlib import closing
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
        # closing(): "with sqlite3.connect()" only commits, it doesn't close the connection.
        with closing(sqlite3.connect(DB_PATH)) as con:
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


def pick_port() -> int:
    """A free port, from PORT up. Ports answered by another Bloom are skipped too: holding the data-folder
    lock means that server belongs to a different data folder (e.g. the free and Pro test copies)."""
    for port in range(PORT, PORT + 20):
        if not port_in_use(port):
            return port
        log.warning("Port %s is used by another application, trying the next one", port)
    raise RuntimeError("No free port found")


_instance_lock = None  # open file whose first byte is locked while this process serves DATA_DIR


def acquire_instance_lock() -> bool:
    """One server per data folder. Two processes migrating and writing the same SQLite file (one still
    starting, another launched meanwhile on the next port) is how a database gets damaged. Windows releases
    the lock when the process ends, even if it crashes."""
    global _instance_lock
    path = DATA_DIR / "instance.lock"
    try:
        f = open(path, "a+b")  # noqa: SIM115 - kept open for the whole process lifetime
    except OSError:
        log.exception("Could not open %s", path)
        return True  # never block the app over the lock file itself
    try:
        if sys.platform == "win32":
            import msvcrt

            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return False
    _instance_lock = f
    return True


def _instance_file() -> Path:
    return DATA_DIR / "instance.json"


def write_instance_port(port: int) -> None:
    try:
        _instance_file().write_text(json.dumps({"port": port, "pid": os.getpid()}), encoding="utf-8")
    except OSError:
        log.exception("Could not write %s", _instance_file())


def running_instance_port() -> int | None:
    """Port of the process that holds this data folder (it may still be starting)."""
    try:
        return int(json.loads(_instance_file().read_text(encoding="utf-8"))["port"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


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


_running_mutex = None  # kept open for the whole process lifetime


def hold_running_mutex() -> None:
    """Named mutex that exists while any copy of the app runs. The installer's update mode waits
    for it to disappear before replacing files (Windows' Restart Manager can't always close us
    without admin rights). Released by Windows when the process ends."""
    global _running_mutex
    if sys.platform != "win32":
        return
    try:
        import ctypes

        _running_mutex = ctypes.windll.kernel32.CreateMutexW(None, False, f"{APP_ID}-app-running")
    except Exception:
        log.exception("Could not create the app mutex")


def main() -> None:
    import webview

    from app import config

    hold_running_mutex()

    running = not acquire_instance_lock()
    if running:
        # Another copy already serves this data folder: just open a window to it (never a second server).
        port = None
        deadline = time.time() + 90
        while time.time() < deadline and port is None:
            port = running_instance_port()
            if port is None:
                time.sleep(0.5)
        port = port or PORT
        log.info("%s already running for %s on %s; opening a window only", APP_DISPLAY_NAME, DATA_DIR, port)
        ready = wait_ready(port, timeout=90)
    else:
        port = pick_port()
        write_instance_port(port)
        threading.Thread(target=run_server, args=("127.0.0.1", port), daemon=True).start()
        ready = wait_ready(port, timeout=90)
    config.PORT = port  # so LAN URL / QR show the real port
    if not ready:
        log.error("Server did not start in time")
    elif not running:
        from app import lan

        lan.enable_switching()
        lan.apply(lan_enabled())
    from desktop_window import WindowApi

    # Frameless: the UI draws its own title bar (drag, minimize, maximize, close).
    min_size = (1024, 680)
    api = WindowApi(DATA_DIR / "window.json", min_size)
    page = {"url": f"http://127.0.0.1:{port}"} if ready else {"html": startup_error_html()}
    window = webview.create_window(
        APP_DISPLAY_NAME,
        **page,
        **api._initial_geometry(1400, 900),
        min_size=min_size,
        text_select=True,
        frameless=True,
        easy_drag=False,
        shadow=True,
        js_api=api,
    )
    api._attach(window)
    if not running:
        # In-app update: once the installer is running, close cleanly so it can replace our files
        # (the installer reopens the app when it's done).
        from app.services import updates

        updates.set_exit_handler(lambda: quit_app(window))
    webview.start(private_mode=False, storage_path=str(DATA_DIR / "webview"))
    if not running:
        shutdown_server()
    os._exit(0)


def shutdown_server(timeout: float = 8.0) -> None:
    """Stops the background jobs and closes the database cleanly (WAL folded in) before the process ends.
    Bounded: a stuck job never keeps the app from closing."""

    def _close() -> None:
        try:
            from app.jobs import stop_jobs

            stop_jobs()
        except Exception:
            log.exception("Could not stop the jobs")
        from app.db import close_cleanly

        close_cleanly()

    t = threading.Thread(target=_close, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        log.warning("Closing the database took more than %s s; exiting anyway", timeout)


def startup_error_html() -> str:
    """Shown instead of the browser's «connection refused» page when the local server didn't start."""
    from html import escape

    log_path = escape(str(DATA_DIR / "app.log"))
    folder = escape(str(DATA_DIR))
    backups = escape(str(DATA_DIR / "backups"))
    return f"""<!doctype html><html lang="es"><meta charset="utf-8"><title>{escape(APP_DISPLAY_NAME)}</title>
<style>
:root {{ color-scheme: light dark; --bg:#FAF7F2; --fg:#2b2118; --muted:#6b5d50; --card:#fff; --line:#e7ded3; --accent:#8B5A2B; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#1c1814; --fg:#f3ece4; --muted:#b9ab9c; --card:#26201a; --line:#3a3128; --accent:#C8874A; }} }}
body {{ margin:0; min-height:100vh; display:grid; place-items:center; background:var(--bg); color:var(--fg);
  font:15px/1.5 "Segoe UI", system-ui, sans-serif; }}
main {{ max-width:560px; margin:24px; padding:28px; background:var(--card); border:1px solid var(--line); border-radius:16px; }}
h1 {{ font-size:22px; margin:0 0 8px; }} p {{ margin:8px 0; color:var(--muted); }}
code {{ display:block; margin-top:4px; padding:8px 10px; border-radius:8px; background:var(--bg); color:var(--fg);
  font:13px Consolas, monospace; overflow-wrap:anywhere; }}
ol {{ padding-left:20px; color:var(--muted); }} strong {{ color:var(--fg); }}
</style>
<main role="alert">
<h1>Bloom no pudo arrancar</h1>
<p>El servidor interno de Bloom no se inició. Tus datos no se borraron.</p>
<ol>
<li>Cerrá esta ventana y volvé a abrir Bloom.</li>
<li>Si vuelve a pasar, mandale a soporte el registro de la app:<code>{log_path}</code></li>
<li>Las copias de seguridad están en:<code>{backups}</code></li>
</ol>
<p>Carpeta de datos: <code>{folder}</code></p>
</main></html>"""


def quit_app(window) -> None:
    """Closes the window (ends webview.start → os._exit) and makes sure the process goes away."""
    log.info("Closing for an update")
    threading.Timer(5.0, lambda: os._exit(0)).start()  # fallback if the window doesn't close
    try:
        window.destroy()
    except Exception:
        log.exception("Could not close the window")
        os._exit(0)


if __name__ == "__main__":
    main()
