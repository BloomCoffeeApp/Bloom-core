"""Personal data rights over the cafe's own database (Ley 25.326): export, anonymize, and retention of the contact
data that online orders copy. The cafe is the data controller; these tools let the owner answer a request.

Anonymizing is NOT deleting the sales: amounts and tickets stay (fiscal obligation). What goes is everything that
identifies the person (name, phone, email, address, birthday, notes, loyalty history, and the personal data copied
into orders, audit entries and cash-movement reasons).
"""

import re
from datetime import timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    CashMovement,
    Customer,
    CustomerAccountMovement,
    LoyaltyStamp,
    LoyaltyTransaction,
    Order,
    Sale,
    SaleItem,
    SalePayment,
    TableDiner,
    User,
    WaiterCall,
    utcnow,
)
from app.services import audit, free_plan
from app.services import settings as settings_svc
from app.services.timeutil import local_today

# Online orders in one of these states are finished: their contact data is no longer needed to serve them.
FINISHED_ORDER_STATES = ("delivered", "rejected", "expired", "cancelled")
ORDER_PERSONAL_FIELDS = ("customer_name", "customer_phone", "address", "address_ref", "invoice_request", "client_ip", "note", "public_key")


def retention_days(db: Session) -> int:
    cfg = settings_svc.get(db, "privacy") or {}
    try:
        return max(0, int(cfg.get("online_order_contact_days", 90)))
    except (TypeError, ValueError):
        return 90


def _digits(s: str | None) -> str:
    return re.sub(r"\D", "", s or "")


def _same_phone(a: str | None, b: str | None) -> bool:
    da, db_ = _digits(a), _digits(b)
    if len(da) < 6 or len(db_) < 6:
        return False
    return da.endswith(db_[-8:]) or db_.endswith(da[-8:])


def _blank_order(o: Order) -> bool:
    changed = False
    for f in ORDER_PERSONAL_FIELDS:
        if getattr(o, f) is not None:
            setattr(o, f, None)
            changed = True
    return changed


# ---------------------------------------------------------------- anonymize


def anonymize(db: Session, c: Customer, user: User, reason: str | None = None) -> dict[str, Any]:
    if c.anonymized_at is not None:
        raise HTTPException(409, "Este cliente ya fue anonimizado")
    if c.balance_cents > 0:
        raise HTTPException(
            409, "El cliente debe plata en cuenta corriente. Cobrala o ajustala antes de anonimizar sus datos"
        )
    phone = c.phone
    counts = {"orders": 0, "sales_notes": 0, "audit": 0, "loyalty": 0}

    # Orders copy the contact data: linked ones, and unlinked ones (e.g. rejected) with the same phone.
    for o in db.scalars(select(Order).where(Order.customer_id == c.id)):
        counts["orders"] += _blank_order(o)
    if _digits(phone):
        for o in db.scalars(select(Order).where(Order.customer_id.is_(None), Order.customer_phone.is_not(None))):
            if _same_phone(o.customer_phone, phone):
                counts["orders"] += _blank_order(o)

    # Free-text notes of its sales can name the person; amounts, items and payments stay.
    for s in db.scalars(select(Sale).where(Sale.customer_id == c.id, Sale.notes.is_not(None))):
        s.notes = None
        counts["sales_notes"] += 1

    # Cash movements written with the name ("Pago cuenta corriente: <name>").
    old_reason = f"Pago cuenta corriente: {c.name}"
    for m in db.scalars(select(CashMovement).where(CashMovement.reason == old_reason)):
        m.reason = "Pago cuenta corriente: cliente anonimizado"

    # Audit entries of this card kept names/phones in their payload.
    for a in db.scalars(select(AuditLog).where(AuditLog.entity == "customer", AuditLog.entity_id == c.id)):
        if a.payload:
            a.payload = {"anonymized": True}
            counts["audit"] += 1

    # Loyalty history has no fiscal value.
    for t in list(db.scalars(select(LoyaltyTransaction).where(LoyaltyTransaction.customer_id == c.id))):
        db.delete(t)
        counts["loyalty"] += 1
    for st in list(db.scalars(select(LoyaltyStamp).where(LoyaltyStamp.customer_id == c.id))):
        db.delete(st)
        counts["loyalty"] += 1

    if c.active:
        free_plan.on_archived(db, "customers", c.id)
    c.name = f"Cliente anonimizado #{c.id}"
    c.phone = c.email = c.address = c.address_ref = c.birthday = c.notes = None
    c.points = 0
    c.active = False
    c.anonymized_at = utcnow()
    audit.log(db, user.id, "anonymize", "customer", c.id, {"reason": (reason or "").strip()[:200] or None, **counts})
    db.commit()
    db.refresh(c)
    return {"id": c.id, "anonymized_at": c.anonymized_at, **counts}


# ---------------------------------------------------------------- export


def export(db: Session, c: Customer, user: User) -> dict[str, Any]:
    if c.anonymized_at is not None:
        raise HTTPException(409, "Este cliente ya fue anonimizado: no quedan datos personales para exportar")
    sales = []
    for s in db.scalars(select(Sale).where(Sale.customer_id == c.id).order_by(Sale.ts, Sale.id)):
        items = db.scalars(select(SaleItem).where(SaleItem.sale_id == s.id).order_by(SaleItem.id))
        pays = db.scalars(select(SalePayment).where(SalePayment.sale_id == s.id).order_by(SalePayment.id))
        sales.append(
            {
                "number": s.number, "ts": s.ts, "status": s.status, "channel": s.channel, "notes": s.notes,
                "subtotal_cents": s.subtotal_cents, "discount_cents": s.discount_cents,
                "delivery_fee_cents": s.delivery_fee_cents, "tip_cents": s.tip_cents, "total_cents": s.total_cents,
                "points_earned": s.points_earned, "points_redeemed": s.points_redeemed,
                "items": [{"name": i.name_snapshot, "qty": i.qty, "unit_price_cents": i.unit_price_cents,
                           "total_cents": i.total_cents, "notes": i.notes} for i in items],
                "payments": [{"method": p.method, "amount_cents": p.amount_cents} for p in pays],
            }
        )
    orders = []
    cands = list(db.scalars(select(Order).where(Order.customer_id == c.id)))
    cands += [o for o in db.scalars(select(Order).where(Order.customer_id.is_(None), Order.customer_phone.is_not(None)))
              if _same_phone(o.customer_phone, c.phone)]
    for o in sorted(cands, key=lambda o: o.created_at):
        orders.append(
            {
                "number": o.number, "source": o.source, "channel": o.channel, "status": o.status,
                "created_at": o.created_at, "customer_name": o.customer_name, "customer_phone": o.customer_phone,
                "address": o.address, "address_ref": o.address_ref, "note": o.note,
                "invoice_request": o.invoice_request, "client_ip": o.client_ip, "total_cents": o.total_cents,
                "delivery_fee_cents": o.delivery_fee_cents,
                "items": [{"name": i.name_snapshot, "qty": i.qty, "unit_price_cents": i.unit_price_cents, "notes": i.notes}
                          for i in o.items],
            }
        )
    out = {
        "exported_at": utcnow(),
        "customer": {
            "id": c.id, "name": c.name, "phone": c.phone, "email": c.email, "address": c.address,
            "address_ref": c.address_ref, "birthday": c.birthday, "notes": c.notes, "points": c.points,
            "balance_cents": c.balance_cents, "credit_limit_cents": c.credit_limit_cents,
            "active": c.active, "created_at": c.created_at,
        },
        "account_movements": [
            {"ts": m.ts, "type": m.type, "method": m.method, "amount_cents": m.amount_cents}
            for m in db.scalars(select(CustomerAccountMovement).where(CustomerAccountMovement.customer_id == c.id).order_by(CustomerAccountMovement.ts, CustomerAccountMovement.id))
        ],
        "loyalty_transactions": [
            {"ts": t.ts, "points": t.points, "reason": t.reason}
            for t in db.scalars(select(LoyaltyTransaction).where(LoyaltyTransaction.customer_id == c.id).order_by(LoyaltyTransaction.ts, LoyaltyTransaction.id))
        ],
        "loyalty_stamps": [
            {"ts": t.ts, "program_id": t.program_id, "stamps": t.stamps, "reason": t.reason}
            for t in db.scalars(select(LoyaltyStamp).where(LoyaltyStamp.customer_id == c.id).order_by(LoyaltyStamp.ts, LoyaltyStamp.id))
        ],
        "sales": sales,
        "online_orders": orders,
        "activity_log": [
            {"ts": a.ts, "action": a.action}
            for a in db.scalars(select(AuditLog).where(AuditLog.entity == "customer", AuditLog.entity_id == c.id).order_by(AuditLog.ts, AuditLog.id))
        ],
    }
    audit.log(db, user.id, "export", "customer", c.id, {"sales": len(sales), "orders": len(orders)})
    db.commit()
    return out


# ---------------------------------------------------------------- retention job

_last_run: list[Any] = [None]


def purge_online_order_contacts(db: Session, now=None) -> int:
    """Blanks the personal data of FINISHED online orders (and stray client IPs) older than the configured days.
    Returns how many online orders were blanked."""
    days = retention_days(db)
    if days <= 0:
        return 0
    cutoff = (now or utcnow()) - timedelta(days=days)
    n = 0
    for o in db.scalars(
        select(Order).where(Order.source == "online", Order.status.in_(FINISHED_ORDER_STATES), Order.created_at < cutoff)
    ):
        n += _blank_order(o)
    # Customers' IP addresses (rate limits only) kept by table / call-the-waiter / any other order: same period.
    ips = 0
    for o in db.scalars(select(Order).where(Order.client_ip.is_not(None), Order.created_at < cutoff)):
        o.client_ip = None
        ips += 1
    for d in db.scalars(select(TableDiner).where(TableDiner.client_ip.is_not(None), TableDiner.last_seen_at < cutoff)):
        d.client_ip = None
        ips += 1
    for w in db.scalars(select(WaiterCall).where(WaiterCall.client_ip.is_not(None), WaiterCall.created_at < cutoff)):
        w.client_ip = None
        ips += 1
    if n or ips:
        audit.log(db, None, "retention_purge", "order", None, {"orders": n, "ips": ips, "days": days})
    db.commit()
    return n


def run_retention_job() -> None:
    """Periodic job (registered in jobs.run_once): once per local day."""
    from app.db import SessionLocal

    today = local_today()
    if _last_run[0] == today:
        return
    with SessionLocal() as db:
        purge_online_order_contacts(db)
    _last_run[0] = today
