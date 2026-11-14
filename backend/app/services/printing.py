"""Direct printing to thermal printers (ESC/POS), without the system print dialog.

Configuration lives in the `printing` setting (see `schemas.printing.PrintingConfig`): the printers
(installed in Windows or on the network at IP:9100), which one is the cashier's (tickets, Z report and
cash drawer) and which one prints each station's kitchen tickets (stations are Pro `orders_pro`).

- Tickets and Z reports are printed on request (the POS/cash screens call the API); when there is no
  printer or it fails, the front falls back to the browser's print dialog.
- Kitchen tickets ("comandas") print by themselves when an order reaches a station that has "Imprimir
  comanda" on and a printer assigned. They are rendered inside the transaction that creates the order
  and sent in a background thread only after it commits (a rolled back sale prints nothing). Failures
  are kept for a while so that station's screen can fall back to the print dialog.
- Disabled (gracefully) in the online demo and outside Windows.
"""

import logging
import secrets
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event
from sqlalchemy.orm import Session

from app import demo
from app.models import CashSession, Order, User
from app.schemas.printing import PrinterCfg, PrintingConfig
from app.services import audit, escpos, printers, settings
from app.services.printers import PrintError

log = logging.getLogger("cafeteria.printing")

SETTING = "printing"
CASH = "efectivo"
FAILURE_TTL_S = 15 * 60
JOBS_KEY = "bloom_print_jobs"

run_async = True  # tests flip it to send queued kitchen tickets synchronously
_locks: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)
_failures: dict[int, dict[str, Any]] = {}
_failures_lock = threading.Lock()
_last_print: dict[str, bool | None] = {"ok": None}


# ---------------------------------------------------------------- availability + config


def availability() -> tuple[bool, str | None]:
    if demo.is_enabled():
        return False, "La impresión directa está desactivada en la demo: se usa el diálogo de impresión."
    if not printers.IS_WINDOWS:
        return False, "La impresión directa está disponible solo en Windows: se usa el diálogo de impresión."
    return True, None


def get_cfg(db: Session) -> dict[str, Any]:
    raw = settings.get(db, SETTING) or {}
    try:
        return PrintingConfig.model_validate(raw).model_dump()
    except ValidationError:
        log.warning("Invalid printing setting, using defaults")
        return PrintingConfig().model_dump()


def save_cfg(db: Session, data: PrintingConfig, user: User) -> dict[str, Any]:
    ok, reason = availability()
    if not ok:
        raise HTTPException(409, reason)
    cfg = data.model_dump()
    seen: set[str] = set()
    for p in cfg["printers"]:
        if not p["id"] or p["id"] in seen:
            p["id"] = secrets.token_hex(4)
        seen.add(p["id"])
    if cfg["cashier_printer"] not in seen:
        cfg["cashier_printer"] = None
    cfg["stations"] = {sid: pid for sid, pid in cfg["stations"].items() if pid in seen and sid.isdigit()}
    settings.put(db, SETTING, cfg)
    audit.log(db, user.id, "update", "setting", None, {"key": SETTING, "printers": len(cfg["printers"])})
    db.commit()
    return cfg


def config_out(db: Session) -> dict[str, Any]:
    from app.services import orders

    ok, reason = availability()
    stations = [{"id": st.id, "name": st.name, "print_tickets": st.print_tickets} for st in orders.active_stations(db)]
    return {**get_cfg(db), "available": ok, "reason": reason, "station_list": stations}


def status(db: Session) -> dict[str, Any]:
    ok, reason = availability()
    cfg = get_cfg(db)
    cashier = ok and _printer(cfg, cfg["cashier_printer"]) is not None
    return {
        "available": ok,
        "reason": reason,
        "ticket_mode": cfg["ticket_mode"],
        "cashier": cashier,
        "cash_drawer": cashier and cfg["cash_drawer"],
    }


def windows_printers() -> list[dict[str, Any]]:
    if not availability()[0]:
        return []
    try:
        return printers.list_windows_printers()
    except PrintError as e:
        raise HTTPException(502, str(e)) from e


def _printer(cfg: dict[str, Any], printer_id: str | None) -> dict[str, Any] | None:
    return next((p for p in cfg["printers"] if p["id"] == printer_id), None) if printer_id else None


def layout(p: dict[str, Any]) -> escpos.Layout:
    return escpos.Layout(chars=p["chars"], codepage=p["codepage"], cut=p["cut"], feed_lines=p["feed_lines"])


# ---------------------------------------------------------------- sending


def transport(p: dict[str, Any]) -> Callable[[bytes, str], None]:
    """How the bytes reach this printer (tests replace it with a fake)."""
    if p["kind"] == "network":
        return lambda data, _doc: printers.send_tcp(p["target"], p["port"], data)
    return lambda data, doc: printers.send_windows(p["target"], data, doc)


def send(p: dict[str, Any], data: bytes, doc_name: str) -> None:
    """One job at a time per printer (interleaved raw jobs would mix tickets)."""
    with _locks[p["id"] or p["target"]]:
        try:
            transport(p)(data, doc_name)
        except Exception:
            _last_print["ok"] = False
            raise
        _last_print["ok"] = True


def last_print_ok() -> bool | None:
    """Did the last job sent since the app started reach the printer? None = nothing printed yet."""
    return _last_print["ok"]


def _send_or_502(p: dict[str, Any], data: bytes, doc_name: str) -> None:
    try:
        send(p, data, doc_name)
    except PrintError as e:
        raise HTTPException(502, f"No se pudo imprimir en «{p['name']}»: {e}") from e
    except Exception as e:  # unexpected (driver, OS): never a 500 for a ticket
        log.exception("Printing failed")
        raise HTTPException(502, f"No se pudo imprimir en «{p['name']}»: {e}") from e


def _cashier(db: Session) -> tuple[dict[str, Any], dict[str, Any]]:
    ok, reason = availability()
    if not ok:
        raise HTTPException(409, reason)
    cfg = get_cfg(db)
    p = _printer(cfg, cfg["cashier_printer"])
    if p is None:
        raise HTTPException(409, "No hay una impresora de caja configurada (Configuración → Impresoras).")
    return cfg, p


# ---------------------------------------------------------------- tickets, drawer, Z, test


def ticket_data(db: Session, sale_id: int) -> dict[str, Any]:
    """Exactly what the HTML ticket gets (`GET /api/sales/{id}/ticket`), as plain dicts."""
    from app.schemas.sales import TicketOut
    from app.services import sales

    return TicketOut.model_validate(sales.ticket(db, sale_id)).model_dump()


def _paid_cash(sale: dict[str, Any]) -> bool:
    return sale["status"] == "completed" and any(p["method"] == CASH and p["amount_cents"] > 0 for p in sale["payments"])


def print_ticket(db: Session, sale_id: int, open_drawer: bool = False) -> dict[str, Any]:
    cfg, p = _cashier(db)
    data = ticket_data(db, sale_id)
    drawer = bool(open_drawer and cfg["cash_drawer"] and _paid_cash(data["sale"]))
    payload = escpos.ticket(data, layout(p), open_drawer=drawer, drawer_pin=cfg["drawer_pin"])
    _send_or_502(p, payload, f"Ticket {data['sale']['number']}")
    return {"ok": True, "printer": p["name"], "drawer": drawer}


def kick_drawer(db: Session, sale_id: int) -> dict[str, Any]:
    """Opens the drawer for a cash sale when the ticket isn't printed ("preguntar"/"nunca")."""
    cfg, p = _cashier(db)
    data = ticket_data(db, sale_id)
    if not (cfg["cash_drawer"] and _paid_cash(data["sale"])):
        return {"ok": True, "printer": p["name"], "drawer": False}
    _send_or_502(p, escpos.drawer_kick(cfg["drawer_pin"]), "Cajón")
    return {"ok": True, "printer": p["name"], "drawer": True}


def print_z(db: Session, session_id: int) -> dict[str, Any]:
    from app.services import cash

    _cfg, p = _cashier(db)
    s = db.get(CashSession, session_id)
    if s is None:
        raise HTTPException(404, "Caja no encontrada")
    payload = escpos.z_report(cash.session_summary(db, s, detail=True), layout(p))
    _send_or_502(p, payload, f"Cierre Z {session_id}")
    return {"ok": True, "printer": p["name"], "drawer": False}


def print_test(db: Session, printer: PrinterCfg) -> dict[str, Any]:
    ok, reason = availability()
    if not ok:
        raise HTTPException(409, reason)
    p = printer.model_dump()
    business = settings.get(db, "business") or {}
    _send_or_502(p, escpos.test_page(p["name"], layout(p), str(business.get("name") or "")), "Prueba")
    return {"ok": True, "printer": p["name"], "drawer": False}


# ---------------------------------------------------------------- kitchen tickets (stations, Pro)


def station_printers(db: Session) -> dict[int, dict[str, Any]]:
    """Station id -> its printer, only when direct printing is available."""
    if not availability()[0]:
        return {}
    cfg = get_cfg(db)
    out = {}
    for sid, pid in cfg["stations"].items():
        p = _printer(cfg, pid)
        if p is not None and sid.isdigit():
            out[int(sid)] = p
    return out


def queue_comandas(db: Session, new_orders: list[Order]) -> None:
    """Renders the kitchen tickets of orders that just reached their stations; they are sent after the
    transaction commits. Never raises: a printer problem must not break a sale."""
    try:
        from app.services import orders

        targets = station_printers(db)
        if not targets:
            return
        stations = {st.id: st for st in orders.active_stations(db) if st.print_tickets}
        t = orders.now()
        jobs = []
        for o in new_orders:
            if o.status in ("pending", "cancelled") or o.station_id not in stations or o.station_id not in targets:
                continue
            p = targets[o.station_id]
            data = orders.serialize(o, t, 100, {}, {})
            jobs.append((o.id, o.station_id, p, escpos.comanda(data, stations[o.station_id].name, layout(p)), o.number))
        if jobs:
            db.info.setdefault(JOBS_KEY, []).extend(jobs)
    except Exception:
        log.exception("Could not prepare kitchen tickets")


def _run_jobs(jobs: list[tuple]) -> None:
    for order_id, station_id, p, payload, number in jobs:
        try:
            send(p, payload, f"Comanda {number}")
        except Exception as e:
            log.warning("Kitchen ticket #%s not printed on %s: %s", number, p["name"], e)
            msg = str(e) if isinstance(e, PrintError) else "error inesperado"
            with _failures_lock:
                _failures[order_id] = {"order_id": order_id, "station_id": station_id, "error": msg, "at": time.monotonic()}


def failures(station_id: int | None) -> list[dict[str, Any]]:
    """Kitchen tickets that couldn't be printed lately (the station's screen prints them itself)."""
    now = time.monotonic()
    with _failures_lock:
        for k in [k for k, v in _failures.items() if now - v["at"] > FAILURE_TTL_S]:
            del _failures[k]
        rows = list(_failures.values())
    return [
        {"order_id": f["order_id"], "error": f["error"]}
        for f in rows
        if station_id is None or f["station_id"] == station_id
    ]


@event.listens_for(Session, "after_commit")
def _after_commit(session: Session) -> None:
    jobs = session.info.pop(JOBS_KEY, None)
    if not jobs:
        return
    if run_async:
        threading.Thread(target=_run_jobs, args=(jobs,), name="bloom-print", daemon=True).start()
    else:
        _run_jobs(jobs)


@event.listens_for(Session, "after_rollback")
def _after_rollback(session: Session) -> None:
    session.info.pop(JOBS_KEY, None)
