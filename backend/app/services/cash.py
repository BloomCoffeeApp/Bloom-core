"""Cash sessions (caja): open, manual movements, live totals and close with counts (arqueo)."""

from collections import defaultdict
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    CashMovement,
    CashSession,
    CashSessionCount,
    PaymentMethod,
    Product,
    ProductCategory,
    Sale,
    SaleItem,
    SalePayment,
    User,
    utcnow,
)
from app.services import audit, settings

CASH = "efectivo"


def get_open_session(db: Session) -> CashSession | None:
    return db.scalar(
        select(CashSession).where(CashSession.status == "open").order_by(CashSession.id.desc()).limit(1)
    )


def require_open_session(db: Session) -> CashSession:
    s = get_open_session(db)
    if s is None:
        raise HTTPException(409, "No hay una caja abierta. Abrí la caja para poder vender.")
    return s


def user_names(db: Session, ids: set[int | None] | None = None) -> dict[int, str]:
    q = select(User.id, User.name)
    clean = {i for i in (ids or set()) if i is not None}
    if ids is not None:
        if not clean:
            return {}
        q = q.where(User.id.in_(clean))
    return {i: n for i, n in db.execute(q)}


def method_names(db: Session) -> dict[str, str]:
    return {c: n for c, n in db.execute(select(PaymentMethod.code, PaymentMethod.name))}


def open_session(db: Session, opening_cents: int, user: User) -> CashSession:
    if get_open_session(db) is not None:
        raise HTTPException(409, "Ya hay una caja abierta")
    s = CashSession(opened_by=user.id, opening_cents=opening_cents, status="open")
    db.add(s)
    db.flush()
    audit.log(db, user.id, "open", "cash_session", s.id, {"opening_cents": opening_cents})
    db.commit()
    return s


def add_movement(db: Session, type_: str, amount_cents: int, reason: str, user: User) -> CashMovement:
    s = require_open_session(db)
    mv = CashMovement(session_id=s.id, type=type_, amount_cents=amount_cents, reason=reason.strip(), user_id=user.id)
    db.add(mv)
    db.flush()
    audit.log(db, user.id, f"movement_{type_}", "cash_session", s.id, {"amount_cents": amount_cents, "reason": reason})
    db.commit()
    return mv


def _live_totals(db: Session, session_id: int) -> dict[str, Any]:
    """Sales/payments aggregates of a session (completed sales only) + voids + movements."""
    pay_rows = db.execute(
        select(SalePayment.method, func.sum(SalePayment.amount_cents), func.count(func.distinct(SalePayment.sale_id)))
        .join(Sale, Sale.id == SalePayment.sale_id)
        .where(Sale.cash_session_id == session_id, Sale.status == "completed")
        .group_by(SalePayment.method)
    ).all()
    by_method = {m: (int(total or 0), int(cnt or 0)) for m, total, cnt in pay_rows}

    sale_row = db.execute(
        select(func.count(Sale.id), func.coalesce(func.sum(Sale.total_cents), 0), func.coalesce(func.sum(Sale.discount_cents), 0))
        .where(Sale.cash_session_id == session_id, Sale.status == "completed", Sale.is_courtesy.is_(False))
    ).one()
    # Courtesies add $0 to the drawer (no payments); shown apart with the menu value given away.
    courtesy_row = db.execute(
        select(func.count(Sale.id), func.coalesce(func.sum(Sale.courtesy_cents), 0))
        .where(Sale.cash_session_id == session_id, Sale.status == "completed", Sale.is_courtesy.is_(True))
    ).one()
    void_row = db.execute(
        select(func.count(Sale.id), func.coalesce(func.sum(Sale.total_cents), 0))
        .where(Sale.cash_session_id == session_id, Sale.status == "voided")
    ).one()
    movements = list(
        db.scalars(select(CashMovement).where(CashMovement.session_id == session_id).order_by(CashMovement.ts))
    )
    mv_in = sum(m.amount_cents for m in movements if m.type == "in")
    mv_out = sum(m.amount_cents for m in movements if m.type == "out")
    return {
        "by_method": by_method,
        "tickets": int(sale_row[0]),
        "sales_total": int(sale_row[1]),
        "discounts": int(sale_row[2]),
        "voided_count": int(void_row[0]),
        "voided_total": int(void_row[1]),
        "courtesy_count": int(courtesy_row[0]),
        "courtesy_cents": int(courtesy_row[1]),
        "movements": movements,
        "mv_in": mv_in,
        "mv_out": mv_out,
    }


def expected_by_method(session: CashSession, totals: dict[str, Any]) -> dict[str, int]:
    """Arqueo: cash = opening + cash sales (already net of change) + ins − outs; others = their sales."""
    exp = {m: total for m, (total, _cnt) in totals["by_method"].items()}
    exp[CASH] = session.opening_cents + exp.get(CASH, 0) + totals["mv_in"] - totals["mv_out"]
    return exp


def session_summary(db: Session, s: CashSession, *, detail: bool = False) -> dict[str, Any]:
    totals = _live_totals(db, s.id)
    names = method_names(db)
    movements = totals["movements"]
    unames = user_names(db, {s.opened_by, s.closed_by, *(m.user_id for m in movements)})

    live_expected = expected_by_method(s, totals)
    stored = {c.payment_method: c for c in s.counts} if s.status == "closed" else {}

    codes = list(dict.fromkeys([CASH, *live_expected.keys(), *stored.keys()]))
    order = {c: i for i, c in enumerate(db.scalars(select(PaymentMethod.code).order_by(PaymentMethod.sort_order)))}
    codes.sort(key=lambda c: order.get(c, 99))

    by_method = []
    diff_total: int | None = 0 if s.status == "closed" else None
    for code in codes:
        sales_cents, cnt = totals["by_method"].get(code, (0, 0))
        if code in stored:
            expected = stored[code].expected_cents
            counted: int | None = stored[code].counted_cents
            diff: int | None = counted - expected
            diff_total = (diff_total or 0) + diff
        else:
            expected = live_expected.get(code, 0)
            counted = None
            diff = None
        by_method.append(
            {
                "method": code,
                "name": names.get(code, code),
                "sales_cents": sales_cents,
                "count": cnt,
                "expected_cents": expected,
                "counted_cents": counted,
                "difference_cents": diff,
            }
        )

    expected_cash = stored[CASH].expected_cents if CASH in stored else live_expected.get(CASH, s.opening_cents)
    out: dict[str, Any] = {
        "id": s.id,
        "status": s.status,
        "opened_at": s.opened_at,
        "opened_by": s.opened_by,
        "opened_by_name": unames.get(s.opened_by),
        "closed_at": s.closed_at,
        "closed_by": s.closed_by,
        "closed_by_name": unames.get(s.closed_by) if s.closed_by else None,
        "opening_cents": s.opening_cents,
        "notes": s.notes,
        "sales_total_cents": totals["sales_total"],
        "tickets": totals["tickets"],
        "avg_ticket_cents": totals["sales_total"] // totals["tickets"] if totals["tickets"] else 0,
        "voided_count": totals["voided_count"],
        "voided_total_cents": totals["voided_total"],
        "courtesy_count": totals["courtesy_count"],
        "courtesy_cents": totals["courtesy_cents"],
        "discounts_cents": totals["discounts"],
        "movements_in_cents": totals["mv_in"],
        "movements_out_cents": totals["mv_out"],
        "expected_cash_cents": expected_cash,
        "difference_cents": diff_total,
        "by_method": by_method,
        "movements": [
            {
                "id": m.id,
                "type": m.type,
                "amount_cents": m.amount_cents,
                "reason": m.reason,
                "user_id": m.user_id,
                "user_name": unames.get(m.user_id) if m.user_id else None,
                "ts": m.ts,
            }
            for m in movements
        ],
    }
    if detail:
        rows = db.execute(
            select(ProductCategory.id, ProductCategory.name, func.sum(SaleItem.qty), func.sum(SaleItem.total_cents))
            .select_from(SaleItem)
            .join(Sale, Sale.id == SaleItem.sale_id)
            .outerjoin(Product, Product.id == SaleItem.product_id)
            .outerjoin(ProductCategory, ProductCategory.id == Product.category_id)
            .where(Sale.cash_session_id == s.id, Sale.status == "completed", Sale.is_courtesy.is_(False))
            .group_by(ProductCategory.id, ProductCategory.name)
            .order_by(func.sum(SaleItem.total_cents).desc())
        ).all()
        out["by_category"] = [
            {"category_id": cid, "name": name or "Sin categoría", "qty": float(qty or 0), "total_cents": int(tot or 0)}
            for cid, name, qty, tot in rows
        ]
        out["business"] = settings.get(db, "business") or {}
    return out


def close_session(db: Session, counts: list[tuple[str, int]], notes: str | None, user: User) -> CashSession:
    s = require_open_session(db)
    totals = _live_totals(db, s.id)
    expected = expected_by_method(s, totals)
    counted = dict(counts)
    valid = set(db.scalars(select(PaymentMethod.code)))
    for code in counted:
        if code not in valid:
            raise HTTPException(400, f"Medio de pago desconocido: {code}")
    codes = list(dict.fromkeys([CASH, *expected.keys(), *counted.keys()]))
    for code in codes:
        exp = expected.get(code, 0)
        s.counts.append(CashSessionCount(payment_method=code, expected_cents=exp, counted_cents=counted.get(code, exp)))
    s.status = "closed"
    s.closed_at = utcnow()
    s.closed_by = user.id
    s.notes = (notes or "").strip() or None
    diff = sum(c.counted_cents - c.expected_cents for c in s.counts)
    audit.log(db, user.id, "close", "cash_session", s.id, {"difference_cents": diff})
    db.commit()
    return s


def list_sessions(db: Session, limit: int = 60, offset: int = 0) -> list[dict[str, Any]]:
    sessions = list(db.scalars(select(CashSession).order_by(CashSession.opened_at.desc()).limit(limit).offset(offset)))
    if not sessions:
        return []
    ids = [s.id for s in sessions]
    agg = {
        sid: (int(cnt or 0), int(tot or 0))
        for sid, cnt, tot in db.execute(
            select(Sale.cash_session_id, func.count(Sale.id), func.sum(Sale.total_cents))
            .where(Sale.cash_session_id.in_(ids), Sale.status == "completed", Sale.is_courtesy.is_(False))
            .group_by(Sale.cash_session_id)
        )
    }
    diffs: dict[int, int] = defaultdict(int)
    for c in db.scalars(select(CashSessionCount).where(CashSessionCount.session_id.in_(ids))):
        diffs[c.session_id] += c.counted_cents - c.expected_cents
    unames = user_names(db, {u for s in sessions for u in (s.opened_by, s.closed_by)})
    return [
        {
            "id": s.id,
            "status": s.status,
            "opened_at": s.opened_at,
            "closed_at": s.closed_at,
            "opened_by_name": unames.get(s.opened_by),
            "closed_by_name": unames.get(s.closed_by) if s.closed_by else None,
            "opening_cents": s.opening_cents,
            "sales_total_cents": agg.get(s.id, (0, 0))[1],
            "tickets": agg.get(s.id, (0, 0))[0],
            "difference_cents": diffs.get(s.id, 0) if s.status == "closed" else None,
        }
        for s in sessions
    ]
