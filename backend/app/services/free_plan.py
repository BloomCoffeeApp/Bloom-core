"""Free plan "option C": what stays usable when the license isn't valid.

Nothing is hidden or deleted. On Free only N items of each kind (N = the free limit of the signed
remote config) are *active for use*; the rest stay visible with a lock and keep their history,
past sales and customer balances, but can't be used (POS, sales, orders, recipes, stock movements,
editing — archiving is always allowed).

Rules (agreed with the owner):
- Default active set: the oldest N (by id, deterministic — never changes on restart).
- The owner can choose which ones ("Elegí tus activos"), stored in the `free_actives` setting:
  {kind: {"ids": [...], "swapped_at": iso | None}}. Without a stored list the default applies.
- The stored list is "materialized" (the default frozen into the setting) before any change made
  on Free, so archiving an active item frees a slot and NOTHING unlocks by itself: the owner creates
  a new one or unlocks a locked one of their choice.
- Taking an item out of the active set while on Free (a swap) has a cooldown
  (`free_limits.swap_cooldown_days`, default 7). Filling a free slot (create or unlock) has none.
- Users: only N active users can log in; there is always an admin among them.
- Pro (valid license) unlocks everything instantly; the selection is kept for next time.

Every endpoint asks this module (`active_ids` / `ensure_usable`), so the rule lives in one place.
A small cache (per database, invalidated on every change) keeps it cheap.
"""

import threading
import time
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.licensing.features import FREE_LIMIT_LABELS, FREE_LIMIT_LABELS_ONE, PRO_LABEL, free_limits, has_feature
from app.licensing.status import current_status
from app.models import Customer, Product, StockItem, User, utcnow
from app.services import audit
from app.services import settings as settings_svc

SETTING = "free_actives"
KINDS: dict[str, Any] = {"products": Product, "customers": Customer, "stock_items": StockItem, "users": User}
KIND_NOUN = {"products": "El producto", "customers": "El cliente", "stock_items": "El insumo", "users": "El usuario"}
_CACHE_S = 30

_lock = threading.Lock()
_cache: dict[tuple[str, str], tuple[float, int, frozenset[int]]] = {}


def invalidate() -> None:
    with _lock:
        _cache.clear()


def limited(kind: str) -> bool:
    """Whether the free caps apply to this kind right now."""
    if kind == "users":
        return not has_feature("users")
    return not current_status().valid


def limit(kind: str) -> int:
    return int(free_limits()[kind])


def cooldown_days() -> int:
    return int(free_limits().get("swap_cooldown_days", 7))


def _db_key(db: Session) -> str:
    try:
        return str(db.get_bind().url)
    except Exception:  # pragma: no cover - unbound session
        return "?"


def _active_rows(db: Session, kind: str) -> list[int]:
    model = KINDS[kind]
    return list(db.scalars(select(model.id).where(model.active.is_(True)).order_by(model.id)))


def _admin_ids(db: Session) -> list[int]:
    return list(db.scalars(select(User.id).where(User.role == "admin", User.active.is_(True)).order_by(User.id)))


def _stored(db: Session) -> dict[str, Any]:
    raw = settings_svc.get(db, SETTING)
    return dict(raw) if isinstance(raw, dict) else {}


def _with_admin(db: Session, ids: list[int], cap: int) -> list[int]:
    admins = _admin_ids(db)
    if not admins or any(i in admins for i in ids):
        return ids
    return sorted([*ids[: max(cap - 1, 0)], admins[0]])


def _compute(db: Session, kind: str, cap: int) -> list[int]:
    active = _active_rows(db, kind)
    entry = _stored(db).get(kind)
    if isinstance(entry, dict) and isinstance(entry.get("ids"), list):
        alive = set(active)
        ids = sorted({i for i in entry["ids"] if isinstance(i, int) and i in alive})[:cap]
    else:
        ids = active[:cap]
    if kind == "users":
        ids = _with_admin(db, ids, cap)
    return ids


def active_ids(db: Session, kind: str) -> frozenset[int] | None:
    """Ids usable right now, or None when there's no restriction (Pro)."""
    if not limited(kind):
        return None
    cap = limit(kind)
    key = (_db_key(db), kind)
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < _CACHE_S and hit[1] == cap:
            return hit[2]
    ids = frozenset(_compute(db, kind, cap))
    with _lock:
        _cache[key] = (now, cap, ids)
    return ids


def is_locked(db: Session, kind: str, item_id: int) -> bool:
    ids = active_ids(db, kind)
    return ids is not None and item_id not in ids


def locked_message(kind: str, name: str | None) -> str:
    cap = limit(kind)
    labels = (FREE_LIMIT_LABELS_ONE if cap == 1 else FREE_LIMIT_LABELS)[kind]
    who = f"{KIND_NOUN[kind]} «{name}»" if name else KIND_NOUN[kind]
    return (
        f"{who} está bloqueado: el plan gratuito permite {cap} {labels} en uso. "
        f"Cambialo en «Elegí tus activos» o pasate a {PRO_LABEL}."
    )


def ensure_usable(db: Session, kind: str, item_id: int, name: str | None = None) -> None:
    """402 when the item is locked by the free plan."""
    if is_locked(db, kind, item_id):
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, locked_message(kind, name))


def ensure_all_usable(db: Session, kind: str, ids: set[int] | list[int]) -> None:
    allowed = active_ids(db, kind)
    if allowed is None:
        return
    bad = [i for i in ids if i not in allowed]
    if bad:
        model = KINDS[kind]
        name = db.scalar(select(model.name).where(model.id == bad[0]))
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, locked_message(kind, name))


# ---------------------------------------------------------------- lifecycle hooks (caller commits)


def _save(db: Session, kind: str, ids: list[int], swapped_at: str | None) -> None:
    stored = _stored(db)
    stored[kind] = {"ids": sorted(set(ids)), "swapped_at": swapped_at}
    settings_svc.put(db, SETTING, stored)
    db.flush()  # a second put in the same transaction must find this row
    invalidate()


def _materialize(db: Session, kind: str) -> tuple[list[int], str | None]:
    """Freezes the current active set into the setting (only matters on Free)."""
    entry = _stored(db).get(kind)
    swapped_at = entry.get("swapped_at") if isinstance(entry, dict) else None
    ids = _compute(db, kind, limit(kind))
    _save(db, kind, ids, swapped_at)
    return ids, swapped_at


def check_can_create(db: Session, kind: str) -> None:
    """402 when every free slot of this kind is in use."""
    ids = active_ids(db, kind)
    if ids is None:
        return
    cap = limit(kind)
    if len(ids) >= cap:
        labels = (FREE_LIMIT_LABELS_ONE if cap == 1 else FREE_LIMIT_LABELS)[kind]
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"El plan gratuito permite hasta {cap} {labels}. Con {PRO_LABEL} no hay límite.",
        )


def on_created(db: Session, kind: str, item_id: int) -> None:
    """A new item created on Free takes a free slot (call after flush, before commit)."""
    if not limited(kind):
        invalidate()
        return
    ids, swapped_at = _materialize(db, kind)
    if item_id not in ids and len(ids) < limit(kind):
        _save(db, kind, [*ids, item_id], swapped_at)


def on_archived(db: Session, kind: str, item_id: int) -> None:
    """Archiving/deleting frees its slot; nothing else unlocks. Call BEFORE flipping `active`."""
    if limited(kind):
        ids, swapped_at = _materialize(db, kind)
        _save(db, kind, [i for i in ids if i != item_id], swapped_at)
        return
    entry = _stored(db).get(kind)
    if isinstance(entry, dict) and item_id in (entry.get("ids") or []):
        _save(db, kind, [i for i in entry["ids"] if i != item_id], entry.get("swapped_at"))
    invalidate()


def on_reactivated(db: Session, kind: str, item_id: int) -> None:
    """Un-archiving on Free takes a free slot if there is one; otherwise it comes back locked.
    Call BEFORE flipping `active` back to True."""
    if not limited(kind):
        invalidate()
        return
    ids, swapped_at = _materialize(db, kind)
    if item_id not in ids and len(ids) < limit(kind):
        _save(db, kind, [*ids, item_id], swapped_at)


# ---------------------------------------------------------------- "Elegí tus activos"


def _next_swap_at(swapped_at: str | None) -> datetime | None:
    if not swapped_at:
        return None
    try:
        at = datetime.fromisoformat(swapped_at) + timedelta(days=cooldown_days())
    except ValueError:
        return None
    return at if at > utcnow() else None


def kind_status(db: Session, kind: str) -> dict[str, Any]:
    total = len(_active_rows(db, kind))
    cap = limit(kind)
    ids = active_ids(db, kind)
    entry = _stored(db).get(kind)
    swapped_at = entry.get("swapped_at") if isinstance(entry, dict) else None
    chosen = isinstance(entry, dict) and isinstance(entry.get("ids"), list)
    preview = sorted(ids) if ids is not None else _compute(db, kind, cap)
    return {
        "kind": kind,
        "limited": ids is not None,
        "limit": cap,
        "total": total,
        "active_ids": preview,
        "used": len(preview),
        "locked": max(total - len(preview), 0) if ids is not None else 0,
        "free_slots": max(cap - len(preview), 0),
        "custom": chosen,
        "next_swap_at": _next_swap_at(swapped_at),
    }


def overview(db: Session) -> dict[str, Any]:
    return {
        "limited": not current_status().valid,
        "cooldown_days": cooldown_days(),
        "kinds": {k: kind_status(db, k) for k in KINDS},
    }


def items(db: Session, kind: str) -> list[dict[str, Any]]:
    """Every non-archived item of a kind, for the chooser."""
    model = KINDS[kind]
    cap = limit(kind)
    current = set(active_ids(db, kind) or _compute(db, kind, cap))
    rows = list(db.scalars(select(model).where(model.active.is_(True)).order_by(model.id)))
    out = []
    for r in rows:
        detail = None
        if kind == "users":
            detail = r.role
        elif kind == "customers":
            detail = r.phone
        elif kind == "stock_items":
            detail = r.unit
        out.append({"id": r.id, "name": r.name, "detail": detail, "active": r.id in current,
                    "is_admin": kind == "users" and r.role == "admin"})
    return out


def choose(db: Session, kind: str, wanted: list[int], user: User) -> dict[str, Any]:
    """Sets the active set of a kind. Unlocking into free slots is free; taking out an item that is
    in use (a swap) on Free respects the cooldown."""
    if kind not in KINDS:
        raise HTTPException(404, "Tipo inexistente")
    cap = limit(kind)
    wanted = sorted(set(wanted))
    if len(wanted) > cap:
        raise HTTPException(400, f"Podés elegir hasta {cap}.")
    alive = set(_active_rows(db, kind))
    if any(i not in alive for i in wanted):
        raise HTTPException(400, "Hay elementos inexistentes o archivados en la selección")
    if kind == "users" and not set(wanted) & set(_admin_ids(db)):
        raise HTTPException(400, "Tiene que quedar al menos un administrador entre los usuarios activos")

    entry = _stored(db).get(kind)
    swapped_at = entry.get("swapped_at") if isinstance(entry, dict) else None
    current = set(_compute(db, kind, cap))
    removed = current - set(wanted)
    if limited(kind) and removed:
        nxt = _next_swap_at(swapped_at)
        if nxt is not None:
            from app.services.timeutil import to_local

            raise HTTPException(
                409,
                f"Podés cambiar un activo por otro una vez cada {cooldown_days()} días. "
                f"Próximo cambio: {to_local(nxt):%d/%m/%Y %H:%M}.",
            )
        swapped_at = utcnow().isoformat()
    _save(db, kind, wanted, swapped_at)
    audit.log(db, user.id, "free_actives", kind, None, {"ids": wanted, "removed": sorted(removed)})
    db.commit()
    if kind == "users":
        from app.auth import revoke_sessions

        for uid in removed:  # locked users are logged out everywhere
            revoke_sessions(db, uid)
        db.commit()
    return kind_status(db, kind)
