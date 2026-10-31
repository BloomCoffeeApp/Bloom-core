"""Background periodic jobs (alerts evaluation, daily backup) in a daemon thread."""

import logging
import threading

log = logging.getLogger("cafeteria.jobs")
_stop = threading.Event()
INTERVAL_S = 300


def run_once() -> None:
    from app.db import SessionLocal
    from app.services import alerts_engine, backup
    from app.services import settings as settings_svc

    with SessionLocal() as db:
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


def _loop() -> None:
    while not _stop.is_set():
        run_once()
        _stop.wait(INTERVAL_S)


def start_jobs() -> None:
    _stop.clear()
    threading.Thread(target=_loop, name="cafe-jobs", daemon=True).start()


def stop_jobs() -> None:
    _stop.set()
