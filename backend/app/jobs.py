"""Background periodic jobs (alerts, daily backup, license, remote config, update check) in daemon threads."""

import logging
import threading
from collections.abc import Callable

log = logging.getLogger("cafeteria.jobs")
_stop = threading.Event()
INTERVAL_S = 300
_extra: list[Callable[[], None]] = []


def register(fn: Callable[[], None]) -> None:
    """Extra periodic job (e.g. from the Pro modules). Idempotent; failures are logged, never raised."""
    if fn not in _extra:
        _extra.append(fn)


def run_once() -> None:
    from app.db import SessionLocal
    from app.services import alerts_engine, backup
    from app.services import settings as settings_svc

    with SessionLocal() as db:
        try:  # this month's fixed expenses first, so their due-date alerts show up right away
            from app.services import expenses

            if expenses.generate_recurring(db):
                db.commit()
        except Exception:
            db.rollback()
            log.exception("recurring expenses failed")
        try:
            alerts_engine.evaluate(db)
            db.commit()
        except Exception:
            db.rollback()
            log.exception("alerts evaluation failed")
        cfg = settings_svc.get(db, "backup")
    try:
        from app.licensing.client import check_pending_checkout, refresh_if_due

        check_pending_checkout()
        refresh_if_due()
    except Exception:
        log.exception("license refresh failed")
    if cfg.get("enabled", True):
        try:
            backup.daily_backup_if_needed(keep=int(cfg.get("keep", 30)))
        except Exception:
            log.exception("daily backup failed")
    for fn in list(_extra):
        try:
            fn()
        except Exception:
            log.exception("job %s failed", getattr(fn, "__qualname__", fn))


def _loop() -> None:
    while not _stop.is_set():
        run_once()
        _stop.wait(INTERVAL_S)


def _updates_loop() -> None:
    """Looks for a new version a little after startup and then every few hours. Offline is fine."""
    from app.services import updates

    if _stop.wait(updates.STARTUP_DELAY_S):
        return
    while not _stop.is_set():
        try:
            if updates.manifest_url():
                updates.check_if_due()
        except Exception:
            log.exception("update check failed")
        _stop.wait(INTERVAL_S)


def _remote_config_loop() -> None:
    """Signed vendor config (update URL, min version, support, announcements): shortly after
    startup and then every 6 h (remote_config decides when it's due). Offline is fine."""
    from app import remote_config

    if _stop.wait(remote_config.STARTUP_DELAY_S):
        return
    while not _stop.is_set():
        try:
            remote_config.refresh_if_due()
        except Exception:
            log.exception("remote config refresh failed")
        _stop.wait(INTERVAL_S)


def start_jobs() -> None:
    _stop.clear()
    from app.services import collect

    collect.start_background()  # polls open QR/Point/link charges (no webhooks reach the cafe PC)
    threading.Thread(target=_loop, name="cafe-jobs", daemon=True).start()
    threading.Thread(target=_remote_config_loop, name="cafe-remote-config", daemon=True).start()
    threading.Thread(target=_updates_loop, name="cafe-updates", daemon=True).start()


def stop_jobs() -> None:
    _stop.set()
    from app.services import collect

    collect.stop_background()
