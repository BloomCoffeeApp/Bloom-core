"""LAN mode: a second listener on 0.0.0.0 next to the always-on 127.0.0.1 one, switchable at runtime.

Only the desktop launcher enables switching (`enable_switching`); in dev/tests the server is
whatever uvicorn was started with and `apply` is a no-op.
"""

import logging
import threading

from app import config

log = logging.getLogger("cafeteria.lan")

_lock = threading.Lock()
_switchable = False
_server = None  # uvicorn.Server listening on the network, when LAN mode is on


def enable_switching() -> None:
    global _switchable
    _switchable = True


def active(enabled: bool) -> bool:
    """Whether phones can reach us now. Outside the launcher, trust the setting (dev/tests)."""
    if not _switchable:
        return enabled
    return _server is not None and _server.started


def apply(enabled: bool) -> None:
    """Starts or stops listening on the network. Never raises: the app keeps working locally."""
    global _server
    if not _switchable:
        return
    with _lock:
        if enabled and _server is None:
            try:
                import uvicorn

                from app.main import app

                # lifespan off: the background jobs already run in the local server
                server = uvicorn.Server(
                    uvicorn.Config(app, host="0.0.0.0", port=config.PORT, lifespan="off", log_level="warning", log_config=None)  # nosec B104 - LAN mode is opt-in
                )
                threading.Thread(target=server.run, name="lan-server", daemon=True).start()
                _server = server
                log.info("LAN mode on (port %s)", config.PORT)
            except Exception:
                log.exception("Could not start the LAN listener")
        elif not enabled and _server is not None:
            _server.should_exit = True
            _server = None
            log.info("LAN mode off")
