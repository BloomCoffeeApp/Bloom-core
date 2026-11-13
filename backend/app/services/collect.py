"""Collecting payments for the cafe: dynamic QR, Point (card terminal), payment links and manual transfers.

The money always goes to the cafe's own account (its Mercado Pago, its bank) — never to Bloom.
Pro feature `payments` ("Cobros con QR, posnet y links de pago"). Contract for other modules: PLAN.md §9.

Design
- `CollectProvider` is the adapter protocol. The core ships `FakeProvider` (tests, the online demo and
  development: approved with "Simular pago"; never offered in the desktop .exe) and the manual transfer
  flow (no provider: the cashier confirms "Pago recibido"). Pro registers the Mercado Pago adapter with
  `register_provider`. Future adapters (Getnet, Payway, MODO, Naranja X / Ualá Bis): see PLAN.md §9.
- A charge is a row in `collect_charges`. Its `ref` is our id (sent to the provider as
  `external_reference`); `ref_type`/`ref_id` say who asked for it. Handlers per `ref_type` react inside
  the SAME transaction that marks the charge approved (`register_handler`). The POS uses `pos_sale`:
  the sale is created only when the payment is approved (payload validated with a dry run first).
- No webhooks reach the cafe PC: open charges are polled (`refresh`): every 2 s during the first minute,
  then every 5 s, then 15 s; failures back off up to 30 s. Polling runs in a background thread
  (`start_background`, desktop app) and also when anyone asks for the status (POS, customer screen,
  other modules), throttled by `next_poll_at`, so it works in the demo/tests without the thread.
- Exactly-once approval: the switch pending -> approved is a conditional UPDATE (`WHERE status='pending'`)
  so two pollers (thread + request) can never create the sale twice.
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Literal, Protocol

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import CollectCharge, CollectRefund, CustomerScreen, PaymentMethod, User, utcnow
from app.services import audit, settings

log = logging.getLogger("cafeteria.collect")

FEATURE = "payments"
Kind = Literal["qr", "link", "point", "transfer"]
KINDS = ("qr", "link", "point", "transfer")
FINAL = ("approved", "rejected", "cancelled", "expired", "refunded")
REF_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SETTING = "collect"
CREDENTIALS_SETTING = "collect_credentials"  # ciphertexts only (services/secret_store.py)
# POS payment method code -> charge kind.
METHOD_KINDS: dict[str, Kind] = {"mp_qr": "qr", "mp_point": "point", "transferencia": "transfer"}
DEFAULTS: dict[str, Any] = {
    "provider": None,  # "mercadopago" | "fake" | None
    "expires_minutes": 10,
    "transfer": {"enabled": False, "alias": "", "cbu": "", "holder": "", "bank": "", "cuit": ""},
    "point_device_id": None,
    "point_device_name": None,
    "default_screen_id": None,
}
APPROVED_SCREEN_SECONDS = 12  # the customer screen shows "¡Pago aprobado!" this long


# ---------------------------------------------------------------- provider protocol


class ProviderError(Exception):
    """A provider call failed. `retryable`: a network/5xx problem (polling keeps trying)."""

    def __init__(self, message: str, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass
class ProviderCharge:
    id: str
    status: str = "pending"  # normalized: pending | approved | rejected | cancelled | expired | refunded
    status_detail: str | None = None
    operation_id: str | None = None  # the provider's payment number, known once it is paid
    qr_data: str | None = None
    url: str | None = None
    expires_at: datetime | None = None
    refunded_cents: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class CollectProvider(Protocol):
    name: str

    def create_qr_charge(self, amount_cents: int, description: str, external_ref: str, *,
                         items: list[dict] | None = None, expires_in_s: int = 600) -> ProviderCharge: ...

    def create_payment_link(self, amount_cents: int, description: str, external_ref: str, *,
                            items: list[dict] | None = None, expires_in_s: int = 1800) -> ProviderCharge: ...

    def send_to_point(self, device_id: str, amount_cents: int, external_ref: str, *,
                      description: str = "") -> ProviderCharge: ...

    def get_status(self, provider_id: str, kind: str) -> ProviderCharge: ...

    def refund(self, provider_id: str, amount_cents: int | None, *, kind: str, idempotency_key: str) -> str | None: ...

    def cancel(self, provider_id: str, kind: str) -> None: ...


@dataclass
class ProviderEntry:
    name: str
    label: str
    build: Callable[[Session], CollectProvider]  # raises ProviderError when not connected
    connected: Callable[[Session], bool]
    kinds: tuple[str, ...] = ("qr", "link", "point")
    info: Callable[[Session], dict] | None = None


_providers: dict[str, ProviderEntry] = {}


def register_provider(entry: ProviderEntry) -> None:
    _providers[entry.name] = entry


def providers() -> dict[str, ProviderEntry]:
    return dict(_providers)


# ---------------------------------------------------------------- fake provider (tests, demo, development)

_fake_status: dict[str, str] = {}
_fake_lock = threading.Lock()


class FakeProvider:
    """Simulated payments: charges stay pending until `simulate` (or a test) changes them."""

    name = "fake"

    def _new(self, prefix: str) -> str:
        pid = f"fake-{prefix}-{secrets.token_hex(6)}"
        with _fake_lock:
            _fake_status[pid] = "pending"
        return pid

    def create_qr_charge(self, amount_cents, description, external_ref, *, items=None, expires_in_s=600):
        pid = self._new("qr")
        # Not a payable EMVCo string on purpose: scanning it in a real wallet must not pay anyone.
        qr = f"BLOOM-PRUEBA|{external_ref}|{amount_cents}"
        return ProviderCharge(pid, qr_data=qr, expires_at=utcnow() + timedelta(seconds=expires_in_s))

    def create_payment_link(self, amount_cents, description, external_ref, *, items=None, expires_in_s=1800):
        pid = self._new("link")
        return ProviderCharge(pid, url=f"https://pago.invalid/{pid}", expires_at=utcnow() + timedelta(seconds=expires_in_s))

    def send_to_point(self, device_id, amount_cents, external_ref, *, description=""):
        return ProviderCharge(self._new("point"), status_detail="at_terminal")

    def get_status(self, provider_id, kind):
        with _fake_lock:
            st = _fake_status.get(provider_id, "pending")
        return ProviderCharge(provider_id, status=st, operation_id=f"FAKE-{provider_id[-8:]}" if st == "approved" else None)

    def refund(self, provider_id, amount_cents, *, kind, idempotency_key):
        return f"fake-refund-{secrets.token_hex(4)}"

    def cancel(self, provider_id, kind):
        with _fake_lock:
            if _fake_status.get(provider_id, "pending") == "pending":
                _fake_status[provider_id] = "cancelled"


def fake_allowed() -> bool:
    """Never in the desktop .exe (a café could think it got paid), except the online demo."""
    from app import demo
    from app.config import FROZEN

    return demo.is_enabled() or not FROZEN or os.environ.get("BLOOM_COLLECT_FAKE") == "1"


def fake_set_status(provider_id: str, status: str) -> None:
    with _fake_lock:
        _fake_status[provider_id] = status


register_provider(ProviderEntry(
    name="fake", label="Modo de prueba (simulado)", build=lambda _db: FakeProvider(),
    connected=lambda _db: fake_allowed(),
))


# ---------------------------------------------------------------- handlers per ref_type


@dataclass
class Handler:
    on_approved: Callable[[Session, CollectCharge], None] | None = None
    on_closed: Callable[[Session, CollectCharge], None] | None = None


_handlers: dict[str, Handler] = {}


def register_handler(ref_type: str, on_approved=None, on_closed=None) -> None:
    """`on_approved(db, charge)` runs in the transaction that marks the charge approved; `on_closed` when it
    expires / is cancelled / rejected. Raise HTTPException (or anything) to flag the charge with `error`."""
    _handlers[ref_type] = Handler(on_approved, on_closed)


# ---------------------------------------------------------------- configuration


def licensed() -> bool:
    from app.licensing import has_feature

    return has_feature(FEATURE)


def require_license() -> None:
    if not licensed():
        from app.licensing.features import PRO_FEATURES, PRO_LABEL

        raise HTTPException(402, f"{PRO_FEATURES[FEATURE]} es parte de {PRO_LABEL}.")


def get_config(db: Session) -> dict[str, Any]:
    from app import demo

    raw = settings.get(db, SETTING) or {}
    cfg = {**DEFAULTS, **{k: v for k, v in raw.items() if k in DEFAULTS}}
    cfg["transfer"] = {**DEFAULTS["transfer"], **(raw.get("transfer") or {})}
    if demo.is_enabled():  # the online demo collects with the simulator and shows a fictional alias
        cfg["provider"] = "fake"
        if not cfg["transfer"]["alias"]:
            cfg["transfer"] = {**cfg["transfer"], "enabled": True, "alias": "cafe.demo.bloom", "holder": "Café Demo (ficticio)"}
    if cfg["provider"] == "fake" and not fake_allowed():
        cfg["provider"] = None
    return cfg


def save_config(db: Session, changes: dict[str, Any], user_id: int | None) -> dict[str, Any]:
    cfg = get_config(db)
    if "provider" in changes:
        prov = changes["provider"]
        if prov is not None and (prov not in _providers or (prov == "fake" and not fake_allowed())):
            raise HTTPException(400, "Proveedor de cobros no disponible")
        cfg["provider"] = prov
    if "transfer" in changes and changes["transfer"] is not None:
        cfg["transfer"] = {**cfg["transfer"], **changes["transfer"]}
        t = cfg["transfer"]
        if t["enabled"] and not (t["alias"].strip() or t["cbu"].strip()):
            raise HTTPException(400, "Para mostrar la transferencia cargá el alias o el CBU/CVU")
    for key in ("expires_minutes", "point_device_id", "point_device_name", "default_screen_id"):
        if key in changes:
            cfg[key] = changes[key]
    settings.put(db, SETTING, cfg)
    sync_methods(db, cfg)
    audit.log(db, user_id, "update", "collect_config", None, {k: v for k, v in changes.items() if k != "transfer"})
    db.commit()
    return cfg


def provider_connected(db: Session, cfg: dict | None = None) -> bool:
    cfg = cfg or get_config(db)
    entry = _providers.get(cfg["provider"] or "")
    if not entry:
        return False
    try:
        return bool(entry.connected(db))
    except Exception:
        log.exception("provider connected() failed")
        return False


def sync_methods(db: Session, cfg: dict | None = None) -> None:
    """QR / Point payment methods on while a provider is connected (and a Point device chosen)."""
    cfg = cfg or get_config(db)
    connected = provider_connected(db, cfg)
    want = {"mp_qr": connected, "mp_point": connected and bool(cfg.get("point_device_id"))}
    for pm in db.scalars(select(PaymentMethod).where(PaymentMethod.code.in_(want))):
        pm.active = want[pm.code]


def get_provider(db: Session) -> tuple[str, CollectProvider]:
    cfg = get_config(db)
    name = cfg["provider"]
    entry = _providers.get(name or "")
    if not entry:
        raise HTTPException(400, "Conectá Mercado Pago en Configuración → Cobros para cobrar con QR, Point o links.")
    try:
        return name, entry.build(db)
    except ProviderError as e:
        raise HTTPException(400, str(e)) from e


def provider_for(db: Session, name: str) -> CollectProvider:
    """The adapter that created a charge (even if the configured provider changed since)."""
    entry = _providers.get(name)
    if entry is None:
        raise ProviderError(f"El proveedor de cobros «{name}» no está disponible en esta edición.", retryable=False)
    return entry.build(db)


def collect_methods(db: Session) -> list[str]:
    """POS payment methods that go through a charge (QR / Point / transfer shown on screen)."""
    if not licensed():
        return []
    cfg = get_config(db)
    out: list[str] = []
    if provider_connected(db, cfg):
        out.append("mp_qr")
        if cfg.get("point_device_id"):
            out.append("mp_point")
    if cfg["transfer"]["enabled"]:
        out.append("transferencia")
    return out


def status(db: Session) -> dict[str, Any]:
    cfg = get_config(db)
    entry = _providers.get(cfg["provider"] or "")
    info: dict[str, Any] = {}
    if entry and entry.info:
        try:
            info = entry.info(db)
        except Exception:
            log.exception("provider info failed")
    return {
        "licensed": licensed(),
        "provider": cfg["provider"],
        "provider_label": entry.label if entry else None,
        "connected": provider_connected(db, cfg),
        "account": info,
        "providers": [
            {"name": e.name, "label": e.label}
            for e in _providers.values() if e.name != "fake" or fake_allowed()
        ],
        "fake_allowed": fake_allowed(),
        "methods": collect_methods(db),
        "transfer": cfg["transfer"],
        "expires_minutes": cfg["expires_minutes"],
        "point_device_id": cfg["point_device_id"],
        "point_device_name": cfg["point_device_name"],
        "default_screen_id": cfg["default_screen_id"],
        "screens": [{"id": s.id, "name": s.name} for s in db.scalars(
            select(CustomerScreen).where(CustomerScreen.active.is_(True)).order_by(CustomerScreen.id))],
    }


# ---------------------------------------------------------------- credentials (encrypted at rest)


def store_credentials(db: Session, provider: str, data: dict[str, Any] | None) -> None:
    """Saves (or with None, forgets) a provider's secrets, encrypted (secret_store). No commit."""
    import json

    from app.services import secret_store

    all_creds = dict(settings.get(db, CREDENTIALS_SETTING) or {})
    if data is None:
        all_creds.pop(provider, None)
    else:
        all_creds[provider] = secret_store.encrypt(json.dumps(data))
    settings.put(db, CREDENTIALS_SETTING, all_creds)


def load_credentials(db: Session, provider: str) -> dict[str, Any] | None:
    import json

    from app.services import secret_store

    stored = (settings.get(db, CREDENTIALS_SETTING) or {}).get(provider)
    if not stored:
        return None
    try:
        return json.loads(secret_store.decrypt(stored))
    except secret_store.SecretStoreError as e:
        raise ProviderError(str(e), retryable=False) from e


# ---------------------------------------------------------------- charges


def new_ref(prefix: str = "bloom") -> str:
    return f"{prefix}-{secrets.token_hex(8)}"


def create_charge(
    db: Session,
    *,
    kind: Kind,
    amount_cents: int,
    description: str,
    ref: str,
    ref_type: str = "external",
    ref_id: int | None = None,
    items: list[dict[str, Any]] | None = None,
    expires_in_s: int | None = None,
    user_id: int | None = None,
    screen_id: int | None = None,
    device_id: str | None = None,
    sale_payload: dict[str, Any] | None = None,
    commit: bool = True,
) -> CollectCharge:
    """Creates a charge at the provider (or a manual transfer) and stores it as `pending`."""
    require_license()
    if kind not in KINDS:
        raise HTTPException(400, "Tipo de cobro inválido")
    if amount_cents <= 0:
        raise HTTPException(400, "El monto a cobrar tiene que ser mayor a cero")
    if not REF_RE.match(ref):
        raise HTTPException(400, "Referencia inválida (letras, números, - y _; hasta 64)")
    if db.scalar(select(CollectCharge.id).where(CollectCharge.ref == ref)):
        raise HTTPException(409, "Ya existe un cobro con esa referencia")
    description = (description or "Compra").strip()[:150]
    cfg = get_config(db)
    if screen_id is not None:
        screen = db.get(CustomerScreen, screen_id)
        if screen is None or not screen.active:
            raise HTTPException(400, "Pantalla del cliente inexistente")
    ttl = expires_in_s or (1800 if kind in ("link", "transfer") else int(cfg["expires_minutes"]) * 60)
    now = utcnow()
    if kind == "transfer":
        if not cfg["transfer"]["enabled"]:
            raise HTTPException(400, "Cargá el alias o CBU/CVU del local en Configuración → Cobros")
        provider_name, pc = "manual", ProviderCharge(id="", expires_at=now + timedelta(seconds=ttl))
    else:
        provider_name, provider = get_provider(db)
        entry = _providers[provider_name]
        if kind not in entry.kinds:
            raise HTTPException(400, f"{entry.label} no admite este tipo de cobro")
        try:
            if kind == "qr":
                pc = provider.create_qr_charge(amount_cents, description, ref, items=items, expires_in_s=ttl)
            elif kind == "link":
                pc = provider.create_payment_link(amount_cents, description, ref, items=items, expires_in_s=ttl)
            else:
                device = device_id or cfg.get("point_device_id")
                if not device:
                    raise HTTPException(400, "Elegí el Point (posnet) en Configuración → Cobros")
                device_id = device
                pc = provider.send_to_point(device, amount_cents, ref, description=description)
        except ProviderError as e:
            raise HTTPException(502, str(e)) from e
    charge = CollectCharge(
        provider=provider_name, kind=kind, ref=ref, ref_type=ref_type, ref_id=ref_id,
        provider_id=pc.id or None, status="pending", status_detail=pc.status_detail,
        amount_cents=amount_cents, description=description, qr_data=pc.qr_data, url=pc.url,
        device_id=device_id, items=items, sale_payload=sale_payload, screen_id=screen_id,
        created_by=user_id, expires_at=pc.expires_at or now + timedelta(seconds=ttl),
        next_poll_at=now + timedelta(seconds=2),
    )
    db.add(charge)
    db.flush()
    if screen_id is not None:
        db.get(CustomerScreen, screen_id).current_charge_id = charge.id
    audit.log(db, user_id, "create", "collect_charge", charge.id,
              {"kind": kind, "amount_cents": amount_cents, "provider": provider_name, "ref_type": ref_type})
    if commit:
        db.commit()
    kick()
    return charge


def get_charge(db: Session, charge_id: int) -> CollectCharge:
    ch = db.get(CollectCharge, charge_id)
    if ch is None:
        raise HTTPException(404, "Cobro no encontrado")
    return ch


def serialize(ch: CollectCharge) -> dict[str, Any]:
    return {
        "id": ch.id, "status": ch.status, "status_detail": ch.status_detail, "kind": ch.kind,
        "provider": ch.provider, "amount_cents": ch.amount_cents, "refunded_cents": ch.refunded_cents,
        "description": ch.description, "qr_data": ch.qr_data, "url": ch.url, "device_id": ch.device_id,
        "expires_at": ch.expires_at, "approved_at": ch.approved_at, "ref": ch.ref, "ref_type": ch.ref_type,
        "ref_id": ch.ref_id, "sale_id": ch.sale_id, "screen_id": ch.screen_id, "error": ch.error,
        "items": ch.items or [], "created_at": ch.created_at,
    }


def charge_status(db: Session, charge_id: int, refresh_now: bool = True) -> dict[str, Any]:
    """Current state of a charge (asks the provider if a poll is due)."""
    ch = get_charge(db, charge_id)
    if refresh_now:
        ch = refresh(db, ch)
    return serialize(ch)


# ---------------------------------------------------------------- polling and transitions

_locks: dict[int, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(charge_id: int) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(charge_id, threading.Lock())


def _poll_interval(ch: CollectCharge, now: datetime) -> timedelta:
    age = (now - ch.created_at).total_seconds()
    return timedelta(seconds=2 if age < 60 else 5 if age < 300 else 15)


def refresh(db: Session, ch: CollectCharge, force: bool = False) -> CollectCharge:
    """Asks the provider for the status if a poll is due (or `force`) and applies the change."""
    if ch.status != "pending":
        return ch
    now = utcnow()
    if not force and ch.next_poll_at and ch.next_poll_at > now:
        return ch
    lock = _lock_for(ch.id)
    if not lock.acquire(blocking=False):  # someone else is polling it right now
        return ch
    try:
        db.refresh(ch)
        if ch.status != "pending":
            return ch
        if ch.provider == "manual":  # transfer: only the cashier approves; it just expires
            if ch.expires_at and ch.expires_at < now:
                _close(db, ch, "expired", "Venció sin confirmar el pago")
            else:
                ch.next_poll_at = now + timedelta(seconds=5)
                db.commit()
            return ch
        try:
            provider = provider_for(db, ch.provider)
            pc = provider.get_status(ch.provider_id or "", ch.kind)
        except (ProviderError, HTTPException) as e:
            ch.poll_failures += 1
            ch.next_poll_at = now + timedelta(seconds=min(30, 2 ** min(ch.poll_failures, 5)))
            db.commit()
            log.warning("collect poll failed for charge %s: %s", ch.id, e)
            return ch
        ch.poll_failures = 0
        if pc.status_detail:
            ch.status_detail = pc.status_detail[:60]
        if pc.operation_id:
            ch.operation_id = str(pc.operation_id)[:40]
        if pc.status == "approved":
            _approve(db, ch)
        elif pc.status in ("rejected", "cancelled", "expired"):
            _close(db, ch, pc.status, None)
        elif pc.status == "refunded":  # refunded from the provider's panel before we saw it approved
            _approve(db, ch)
            db.refresh(ch)
            ch.refunded_cents = ch.amount_cents
            ch.status = "refunded"
            db.commit()
        elif ch.expires_at and ch.expires_at + timedelta(seconds=30) < now:
            # Our deadline passed and the provider still says pending: cancel there (best effort) and close.
            try:
                provider.cancel(ch.provider_id or "", ch.kind)
            except ProviderError:
                log.warning("could not cancel expired charge %s at the provider", ch.id)
            _close(db, ch, "expired", "Venció sin pagarse")
        else:
            ch.next_poll_at = now + _poll_interval(ch, now)
            db.commit()
        return ch
    finally:
        lock.release()


def _approve(db: Session, ch: CollectCharge, confirmed_by: int | None = None) -> None:
    """pending -> approved exactly once, running the ref_type handler in the same transaction."""
    now = utcnow()
    db.flush()  # keep in-memory changes (poll bookkeeping) made before the conditional UPDATE
    res = db.execute(
        update(CollectCharge)
        .where(CollectCharge.id == ch.id, CollectCharge.status == "pending")
        .values(status="approved", approved_at=now, closed_at=now, confirmed_by=confirmed_by, error=None, updated_at=now)
        .execution_options(synchronize_session=False)
    )
    if res.rowcount != 1:
        db.rollback()
        return
    db.refresh(ch)
    handler = _handlers.get(ch.ref_type)
    try:
        if handler and handler.on_approved:
            handler.on_approved(db, ch)
        audit.log(db, confirmed_by, "approve", "collect_charge", ch.id, {"amount_cents": ch.amount_cents, "sale_id": ch.sale_id})
        db.commit()
    except Exception as e:
        db.rollback()
        msg = e.detail if isinstance(e, HTTPException) else str(e) or e.__class__.__name__
        log.warning("charge %s approved but its handler failed: %s", ch.id, msg)
        db.execute(
            update(CollectCharge)
            .where(CollectCharge.id == ch.id, CollectCharge.status == "pending")
            .values(status="approved", approved_at=now, closed_at=now, confirmed_by=confirmed_by,
                    error=str(msg)[:300], updated_at=now)
            .execution_options(synchronize_session=False)
        )
        db.commit()
        db.refresh(ch)


def retry_handler(db: Session, charge_id: int, user_id: int | None = None) -> CollectCharge:
    """Approved charge whose follow-up failed (e.g. the cash register was closed): try again."""
    ch = get_charge(db, charge_id)
    if ch.status != "approved" or not ch.error:
        raise HTTPException(400, "Este cobro no tiene nada pendiente")
    handler = _handlers.get(ch.ref_type)
    try:
        if handler and handler.on_approved:
            handler.on_approved(db, ch)
        ch.error = None
        audit.log(db, user_id, "retry", "collect_charge", ch.id, {"sale_id": ch.sale_id})
        db.commit()
    except Exception:
        db.rollback()
        raise
    return ch


def _close(db: Session, ch: CollectCharge, status_: str, detail: str | None) -> None:
    now = utcnow()
    db.flush()
    res = db.execute(
        update(CollectCharge)
        .where(CollectCharge.id == ch.id, CollectCharge.status == "pending")
        .values(status=status_, closed_at=now, updated_at=now, **({"status_detail": detail} if detail else {}))
        .execution_options(synchronize_session=False)
    )
    if res.rowcount != 1:
        db.rollback()
        return
    db.refresh(ch)
    handler = _handlers.get(ch.ref_type)
    if handler and handler.on_closed:
        try:
            handler.on_closed(db, ch)
        except Exception:
            log.exception("on_closed handler failed for charge %s", ch.id)
    db.commit()


def cancel_charge(db: Session, charge_id: int, user_id: int | None = None) -> CollectCharge:
    ch = get_charge(db, charge_id)
    if ch.status != "pending":
        return ch
    if ch.provider != "manual":
        # Last look first: if the customer just paid, don't cancel a payment that went through.
        ch = refresh(db, ch, force=True)
        if ch.status != "pending":
            return ch
        try:
            provider = provider_for(db, ch.provider)
            provider.cancel(ch.provider_id or "", ch.kind)
        except (ProviderError, HTTPException) as e:
            log.warning("cancel at provider failed for charge %s: %s", ch.id, e)
    _close(db, ch, "cancelled", "Cancelado en la caja")
    audit.log(db, user_id, "cancel", "collect_charge", ch.id, None)
    db.commit()
    return ch


def confirm_manual(db: Session, charge_id: int, user_id: int | None) -> CollectCharge:
    """Transfer: the cashier saw the money in the bank/wallet app ("Pago recibido")."""
    ch = get_charge(db, charge_id)
    if ch.provider != "manual":
        raise HTTPException(400, "Este cobro se confirma solo cuando el proveedor aprueba el pago")
    if ch.status != "pending":
        raise HTTPException(409, "Este cobro ya no está pendiente")
    _approve(db, ch, confirmed_by=user_id)
    db.refresh(ch)
    return ch


def simulate(db: Session, charge_id: int, status_: str) -> CollectCharge:
    """Fake provider only (tests, demo, development): the 'customer' pays / is rejected."""
    ch = get_charge(db, charge_id)
    if ch.provider != "fake" or not fake_allowed():
        raise HTTPException(400, "Solo se puede simular un cobro de prueba")
    fake_set_status(ch.provider_id or "", status_)
    return refresh(db, ch, force=True)


def refund(db: Session, charge_id: int, amount_cents: int | None = None, user_id: int | None = None,
           reason: str | None = None) -> CollectCharge:
    """Gives money back through the provider. None = everything left; partial refunds add up."""
    require_license()
    ch = get_charge(db, charge_id)
    if ch.status != "approved":
        raise HTTPException(400, "Solo se puede devolver un cobro aprobado")
    if ch.provider == "manual":
        raise HTTPException(400, "Una transferencia se devuelve desde tu banco o billetera")
    left = ch.amount_cents - ch.refunded_cents
    amount = left if amount_cents is None else amount_cents
    if amount <= 0 or amount > left:
        raise HTTPException(400, f"Podés devolver hasta ${left / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    full = amount == ch.amount_cents and ch.refunded_cents == 0
    key = f"{ch.ref}-refund-{ch.refunded_cents}-{amount}"
    try:
        provider = provider_for(db, ch.provider)
        refund_id = provider.refund(ch.provider_id or "", None if full else amount, kind=ch.kind, idempotency_key=key)
    except ProviderError as e:
        raise HTTPException(502, str(e)) from e
    db.add(CollectRefund(charge_id=ch.id, amount_cents=amount, provider_refund_id=refund_id,
                         reason=(reason or "").strip()[:200] or None, user_id=user_id))
    ch.refunded_cents += amount
    if ch.refunded_cents >= ch.amount_cents:
        ch.status = "refunded"
    audit.log(db, user_id, "refund", "collect_charge", ch.id, {"amount_cents": amount, "sale_id": ch.sale_id, "reason": reason})
    db.commit()
    return ch


def refunds_of(db: Session, charge_id: int) -> list[CollectRefund]:
    return list(db.scalars(select(CollectRefund).where(CollectRefund.charge_id == charge_id).order_by(CollectRefund.id)))


def poll_due(db: Session, limit: int = 20) -> int:
    """One pass over open charges whose poll is due. Returns how many are still open."""
    now = utcnow()
    due = list(db.scalars(
        select(CollectCharge).where(CollectCharge.status == "pending", CollectCharge.next_poll_at <= now)
        .order_by(CollectCharge.next_poll_at).limit(limit)
    ))
    for ch in due:
        try:
            refresh(db, ch)
        except Exception:
            db.rollback()
            log.exception("polling charge %s failed", ch.id)
    return len(list(db.scalars(select(CollectCharge.id).where(CollectCharge.status == "pending"))))


# ---------------------------------------------------------------- background poller (desktop app)

_wake = threading.Event()
_stop = threading.Event()
_thread: threading.Thread | None = None


def kick() -> None:
    """A charge was opened: make sure the poller is awake."""
    _wake.set()


def _loop() -> None:
    from app.db import SessionLocal

    while not _stop.is_set():
        open_count = 0
        try:
            with SessionLocal() as db:
                open_count = poll_due(db)
        except Exception:
            log.exception("collect poller pass failed")
        if open_count:
            _stop.wait(1)
        else:  # nothing open: sleep until a charge is created (or check again in a while)
            _wake.wait(60)
            _wake.clear()


def start_background() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="collect-poller", daemon=True)
    _thread.start()


def stop_background() -> None:
    _stop.set()
    _wake.set()


# ---------------------------------------------------------------- POS checkout


def pos_charge(db: Session, sale_data: Any, method: str, user: User, screen_id: int | None) -> CollectCharge:
    """POS: validates the sale with a dry run, then opens a charge; the sale is created on approval."""
    from app.services import sales as sales_svc

    require_license()
    kind = METHOD_KINDS.get(method)
    if kind is None or method not in collect_methods(db):
        raise HTTPException(400, "Ese medio de pago no se cobra con QR, Point ni transferencia en pantalla")
    pays = [p for p in sale_data.payments if p.method == method and p.amount_cents > 0]
    if len(pays) != 1:
        raise HTTPException(400, "Indicá un solo pago con ese medio")
    if sale_data.is_courtesy:
        raise HTTPException(400, "Una cortesía no se cobra")
    amount = pays[0].amount_cents
    # Dry run: every rule of the sale (cash open, prices, stock, discounts, totals) without saving.
    try:
        sale = sales_svc._create_sale(db, sale_data, user)
        items = [
            {"name": it.name_snapshot + (f" ({it.size_name})" if it.size_name else ""), "qty": it.qty,
             "total_cents": it.total_cents}
            for it in sale.items
        ]
    finally:
        db.rollback()
    biz = (settings.get(db, "business") or {}).get("name") or "Compra"
    return create_charge(
        db, kind=kind, amount_cents=amount, description=f"{biz} - compra"[:150], ref=new_ref("pos"),
        ref_type="pos_sale", items=items, user_id=user.id, screen_id=screen_id,
        sale_payload=sale_data.model_dump(mode="json"),
    )


def _pos_on_approved(db: Session, ch: CollectCharge) -> None:
    from app.schemas.sales import SaleIn
    from app.services import sales as sales_svc

    if ch.sale_id is not None or not ch.sale_payload:
        return
    user = db.get(User, ch.created_by) if ch.created_by else None
    if user is None:
        raise HTTPException(400, "El usuario que inició el cobro ya no existe")
    sale = sales_svc._create_sale(db, SaleIn.model_validate(ch.sale_payload), user)
    ch.sale_id = sale.id


register_handler("pos_sale", on_approved=_pos_on_approved)


def charge_for_sale(db: Session, sale_id: int) -> CollectCharge | None:
    return db.scalar(select(CollectCharge).where(CollectCharge.sale_id == sale_id).order_by(CollectCharge.id.desc()))


# ---------------------------------------------------------------- customer screens


def screens(db: Session) -> list[CustomerScreen]:
    return list(db.scalars(select(CustomerScreen).order_by(CustomerScreen.id)))


def create_screen(db: Session, name: str, user_id: int | None) -> CustomerScreen:
    s = CustomerScreen(name=name.strip()[:60] or "Pantalla", token=secrets.token_urlsafe(24))
    db.add(s)
    db.flush()
    audit.log(db, user_id, "create", "customer_screen", s.id, {"name": s.name})
    db.commit()
    return s


def update_screen(db: Session, screen_id: int, user_id: int | None, name: str | None = None,
                  active: bool | None = None, rotate: bool = False) -> CustomerScreen:
    s = db.get(CustomerScreen, screen_id)
    if s is None:
        raise HTTPException(404, "Pantalla no encontrada")
    if name is not None:
        s.name = name.strip()[:60] or s.name
    if active is not None:
        s.active = active
    if rotate:
        s.token = secrets.token_urlsafe(24)
    audit.log(db, user_id, "update", "customer_screen", s.id, {"name": name, "active": active, "rotate": rotate})
    db.commit()
    return s


def delete_screen(db: Session, screen_id: int, user_id: int | None) -> None:
    s = db.get(CustomerScreen, screen_id)
    if s is None:
        raise HTTPException(404, "Pantalla no encontrada")
    db.execute(update(CollectCharge).where(CollectCharge.screen_id == s.id).values(screen_id=None))
    db.delete(s)
    cfg = get_config(db)
    if cfg.get("default_screen_id") == screen_id:
        settings.put(db, SETTING, {**cfg, "default_screen_id": None})
    audit.log(db, user_id, "delete", "customer_screen", screen_id, None)
    db.commit()


@lru_cache(maxsize=64)
def _qr_data_url(text: str) -> str:
    import base64

    from app.services.system import qr_png

    return "data:image/png;base64," + base64.b64encode(qr_png(text)).decode()


def screen_state(db: Session, token: str) -> dict[str, Any]:
    """What a customer screen shows now (public, by its secret token)."""
    s = db.scalar(select(CustomerScreen).where(CustomerScreen.token == token)) if token else None
    if s is None or not s.active:
        raise HTTPException(404, "Pantalla no registrada. Pedile al encargado el link de esta pantalla.")
    now = utcnow()
    if not s.last_seen_at or (now - s.last_seen_at).total_seconds() > 30:
        s.last_seen_at = now
        db.commit()
    biz = settings.get(db, "business") or {}
    out: dict[str, Any] = {"screen": s.name, "business_name": biz.get("name") or "", "state": "idle", "charge": None}
    if not licensed():
        return out
    ch = db.get(CollectCharge, s.current_charge_id) if s.current_charge_id else None
    if ch is None:
        return out
    ch = refresh(db, ch)
    if ch.status == "pending":
        state = "pending"
    elif ch.status == "approved" and ch.approved_at and (now - ch.approved_at).total_seconds() < APPROVED_SCREEN_SECONDS:
        state = "approved"
    elif ch.status in ("cancelled", "expired", "rejected") and ch.closed_at and (now - ch.closed_at).total_seconds() < 6:
        state = ch.status
    else:
        return out
    cfg = get_config(db)
    charge: dict[str, Any] = {
        "id": ch.id, "kind": ch.kind, "amount_cents": ch.amount_cents, "items": ch.items or [],
        "expires_at": ch.expires_at, "fake": ch.provider == "fake",
    }
    if state == "pending":
        if ch.kind == "qr" and ch.qr_data:
            charge["qr_png"] = _qr_data_url(ch.qr_data)
        elif ch.kind == "link" and ch.url:
            charge["qr_png"] = _qr_data_url(ch.url)
        elif ch.kind == "transfer":
            t = cfg["transfer"]
            charge["transfer"] = {k: t[k] for k in ("alias", "cbu", "holder", "bank", "cuit")}
    out["state"] = state
    out["charge"] = charge
    return out
