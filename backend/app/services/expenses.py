"""Business expenses ("Gestión de gastos"): categories, monthly recurring expenses, paying them (optionally
with cash taken from the open drawer, in the same transaction) and the month result.

Free edition: recording expenses and the month's "ganancia real" (dashboard card). The full result
report (month by month, comparison, categories, export) is Pro `reports` (bloom_pro/services/reports.py),
built on the functions here.

Dates: `Expense.date` is a LOCAL calendar date (accrual). Periods are "YYYY-MM" strings.
"""

import re
import secrets
from calendar import monthrange
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.config import DATA_DIR
from app.models import (
    CashMovement,
    CashSession,
    Expense,
    ExpenseCategory,
    PaymentMethod,
    RecurringExpense,
    Sale,
    StockItem,
    StockMovement,
    User,
    utcnow,
)
from app.services import audit, idempotency
from app.services.timeutil import local_today, range_bounds_utc, to_utc_naive

CASH = "efectivo"
PERIOD_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
MAX_CATCH_UP_MONTHS = 24  # an install left off for years doesn't flood the list

DEFAULT_CATEGORIES: list[tuple[str, str]] = [
    ("Alquiler", "fixed"),
    ("Servicios (luz, gas, agua, internet)", "fixed"),
    ("Sueldos y cargas sociales", "fixed"),
    ("Impuestos y tasas", "fixed"),
    ("Abonos y suscripciones", "fixed"),
    ("Mantenimiento y reparaciones", "variable"),
    ("Limpieza y descartables", "variable"),
    ("Publicidad", "variable"),
    ("Comisiones y gastos bancarios", "variable"),
    ("Otros", "variable"),
]


# ---------------------------------------------------------------- periods


def period_of(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def parse_period(p: str | None) -> str:
    """Validated "YYYY-MM" (current month when empty)."""
    if not p:
        return period_of(local_today())
    if not PERIOD_RE.match(p):
        raise HTTPException(400, "Mes inválido (usá AAAA-MM)")
    return p


def add_months(p: str, n: int) -> str:
    y, m = int(p[:4]), int(p[5:7])
    idx = y * 12 + (m - 1) + n
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def period_bounds(p: str) -> tuple[date, date]:
    y, m = int(p[:4]), int(p[5:7])
    return date(y, m, 1), date(y, m, monthrange(y, m)[1])


def due_date_in(p: str, day: int) -> date:
    y, m = int(p[:4]), int(p[5:7])
    return date(y, m, min(max(day, 1), monthrange(y, m)[1]))


# ---------------------------------------------------------------- categories


def ensure_categories(db: Session) -> None:
    """Default categories on a database that has none (the migration inserts them; fresh test DBs don't)."""
    if db.scalar(select(func.count(ExpenseCategory.id))):
        return
    db.add_all(ExpenseCategory(name=n, kind=k, sort_order=i) for i, (n, k) in enumerate(DEFAULT_CATEGORIES, start=1))
    db.flush()


def list_categories(db: Session) -> list[ExpenseCategory]:
    ensure_categories(db)
    db.commit()
    return list(db.scalars(select(ExpenseCategory).order_by(ExpenseCategory.active.desc(), ExpenseCategory.sort_order, ExpenseCategory.name)))


def _check_category_name(db: Session, name: str, exclude_id: int | None = None) -> str:
    name = name.strip()
    if not name:
        raise HTTPException(400, "Poné un nombre para la categoría")
    q = select(ExpenseCategory.id).where(func.lower(ExpenseCategory.name) == name.lower())
    if exclude_id is not None:
        q = q.where(ExpenseCategory.id != exclude_id)
    if db.scalar(q):
        raise HTTPException(409, f"Ya existe la categoría «{name}»")
    return name


def create_category(db: Session, name: str, kind: str, user: User) -> ExpenseCategory:
    name = _check_category_name(db, name)
    order = int(db.scalar(select(func.max(ExpenseCategory.sort_order))) or 0) + 1
    c = ExpenseCategory(name=name, kind=kind, sort_order=order)
    db.add(c)
    db.flush()
    audit.log(db, user.id, "create", "expense_category", c.id, {"name": name})
    db.commit()
    return c


def update_category(db: Session, category_id: int, changes: dict[str, Any], user: User) -> ExpenseCategory:
    c = db.get(ExpenseCategory, category_id)
    if c is None:
        raise HTTPException(404, "Categoría no encontrada")
    if changes.get("name") is not None:
        changes["name"] = _check_category_name(db, changes["name"], c.id)
    for k, v in changes.items():
        if v is not None:
            setattr(c, k, v)
    audit.log(db, user.id, "update", "expense_category", c.id, changes)
    db.commit()
    return c


def _category(db: Session, category_id: int) -> ExpenseCategory:
    c = db.get(ExpenseCategory, category_id)
    if c is None:
        raise HTTPException(400, "Elegí una categoría")
    if not c.active:
        raise HTTPException(400, f"La categoría «{c.name}» está archivada")
    return c


def _method(db: Session, code: str | None) -> str | None:
    if not code:
        return None
    if db.scalar(select(PaymentMethod.id).where(PaymentMethod.code == code)) is None:
        raise HTTPException(400, f"Medio de pago desconocido: {code}")
    return code


# ---------------------------------------------------------------- cash drawer


def _reason(e: Expense) -> str:
    return f"Gasto: {e.description}"[:200]


def _cash_out(db: Session, e: Expense, user: User) -> None:
    """Cash egreso of the open drawer for this expense, in the caller's transaction."""
    from app.services.cash import get_open_session

    s = get_open_session(db)
    if s is None:
        raise HTTPException(409, "No hay una caja abierta. Abrila para sacar la plata de la caja o elegí otro medio de pago.")
    mv = CashMovement(session_id=s.id, type="out", amount_cents=e.amount_cents, reason=_reason(e), user_id=user.id)
    db.add(mv)
    db.flush()
    e.cash_movement_id = mv.id
    e.payment_method = CASH
    audit.log(db, user.id, "movement_out", "cash_session", s.id, {"amount_cents": e.amount_cents, "reason": mv.reason, "expense": True})


def _movement_session(db: Session, e: Expense) -> tuple[CashMovement, CashSession] | None:
    if e.cash_movement_id is None:
        return None
    mv = db.get(CashMovement, e.cash_movement_id)
    if mv is None:
        return None
    return mv, db.get(CashSession, mv.session_id)


CLOSED_DRAWER = ("Este gasto salió de una caja que ya se cerró: no se puede cambiar el monto, el medio de pago ni "
                 "borrarlo. Si hubo un error, corregilo con un movimiento en la caja actual.")


# ---------------------------------------------------------------- expenses


def _get(db: Session, expense_id: int) -> Expense:
    e = db.get(Expense, expense_id)
    if e is None:
        raise HTTPException(404, "Gasto no encontrado")
    return e


def create_expense(db: Session, data: dict[str, Any], user: User, _key: idempotency.KeyHash | None = None) -> Expense:
    cat = _category(db, data["category_id"])
    status = data.get("status") or "paid"
    when = data.get("date") or local_today()
    e = Expense(
        category_id=cat.id,
        kind=data.get("kind") or cat.kind,
        description=data["description"].strip(),
        amount_cents=data["amount_cents"],
        date=when,
        status=status,
        due_date=(data.get("due_date") or when) if status == "pending" else data.get("due_date"),
        payment_method=_method(db, data.get("payment_method")),
        notes=(data.get("notes") or "").strip() or None,
        user_id=user.id,
    )
    if not e.description:
        raise HTTPException(400, "Escribí un concepto")
    db.add(e)
    db.flush()
    if status == "paid":
        e.paid_at = utcnow()
        if data.get("from_cash"):
            _cash_out(db, e, user)
    elif data.get("from_cash"):
        raise HTTPException(400, "Un gasto pendiente todavía no sale de la caja")
    audit.log(db, user.id, "create", "expense", e.id, {"amount_cents": e.amount_cents, "status": status,
                                                       "from_cash": e.cash_movement_id is not None})
    idempotency.record_if(db, _key, "expense_create", user, e.id)
    db.commit()
    return e


def update_expense(db: Session, expense_id: int, changes: dict[str, Any], user: User) -> Expense:
    e = _get(db, expense_id)
    if "category_id" in changes and changes["category_id"] is not None and changes["category_id"] != e.category_id:
        _category(db, changes["category_id"])
    if "payment_method" in changes:
        changes["payment_method"] = _method(db, changes["payment_method"])
    if "description" in changes and changes["description"] is not None:
        changes["description"] = changes["description"].strip()
        if not changes["description"]:
            raise HTTPException(400, "Escribí un concepto")
    linked = _movement_session(db, e)
    if linked:
        mv, session = linked
        amount_changes = changes.get("amount_cents") not in (None, e.amount_cents)
        leaves_cash = "payment_method" in changes and changes["payment_method"] != CASH
        if amount_changes or leaves_cash:
            if session.status != "open":
                raise HTTPException(409, CLOSED_DRAWER)
            if leaves_cash:
                db.delete(mv)
                e.cash_movement_id = None
            else:
                mv.amount_cents = changes["amount_cents"]
    for k, v in changes.items():
        if k == "notes":
            e.notes = (v or "").strip() or None
        elif k in ("due_date", "payment_method"):
            setattr(e, k, v)
        elif v is not None:
            setattr(e, k, v)
    if e.cash_movement_id is not None:
        mv = db.get(CashMovement, e.cash_movement_id)
        if mv is not None:
            mv.reason = _reason(e)
    audit.log(db, user.id, "update", "expense", e.id, {k: str(v) for k, v in changes.items()})
    db.commit()
    return e


def pay_expense(db: Session, expense_id: int, data: dict[str, Any], user: User, _key: idempotency.KeyHash | None = None) -> Expense:
    e = _get(db, expense_id)
    if e.status == "paid":
        raise HTTPException(409, "Este gasto ya está pagado")
    if data.get("amount_cents"):
        e.amount_cents = data["amount_cents"]
    e.payment_method = _method(db, data.get("payment_method")) or e.payment_method
    e.status = "paid"
    e.paid_at = utcnow()
    if data.get("from_cash"):
        _cash_out(db, e, user)
    audit.log(db, user.id, "pay", "expense", e.id, {"amount_cents": e.amount_cents, "from_cash": bool(data.get("from_cash"))})
    idempotency.record_if(db, _key, "expense_pay", user, e.id)
    db.commit()
    return e


def delete_expense(db: Session, expense_id: int, user: User) -> None:
    e = _get(db, expense_id)
    linked = _movement_session(db, e)
    if linked:
        mv, session = linked
        if session.status != "open":
            raise HTTPException(409, CLOSED_DRAWER)
        db.delete(mv)
    receipt = receipt_file(e)
    audit.log(db, user.id, "delete", "expense", e.id, {"amount_cents": e.amount_cents, "description": e.description})
    db.delete(e)
    db.commit()
    if receipt is not None:
        receipt.unlink(missing_ok=True)


def serialize(e: Expense, cats: dict[int, str], methods: dict[str, str], today: date | None = None) -> dict[str, Any]:
    today = today or local_today()
    return {
        "id": e.id,
        "category_id": e.category_id,
        "category_name": cats.get(e.category_id, "—"),
        "kind": e.kind,
        "description": e.description,
        "amount_cents": e.amount_cents,
        "date": e.date,
        "due_date": e.due_date,
        "status": e.status,
        "overdue": e.status == "pending" and e.due_date is not None and e.due_date < today,
        "paid_at": e.paid_at,
        "payment_method": e.payment_method,
        "payment_method_name": methods.get(e.payment_method or "", e.payment_method),
        "from_cash": e.cash_movement_id is not None,
        "recurring_id": e.recurring_id,
        "period": e.period,
        "has_receipt": bool(e.receipt_path),
        "notes": e.notes,
        "created_at": e.created_at,
    }


def _names(db: Session) -> tuple[dict[int, str], dict[str, str]]:
    cats = dict(db.execute(select(ExpenseCategory.id, ExpenseCategory.name)).all())
    methods = dict(db.execute(select(PaymentMethod.code, PaymentMethod.name)).all())
    return cats, methods


def get_expense(db: Session, expense_id: int) -> dict[str, Any]:
    cats, methods = _names(db)
    return serialize(_get(db, expense_id), cats, methods)


def list_expenses(
    db: Session, period: str, *, status: str | None = None, category_id: int | None = None, kind: str | None = None
) -> dict[str, Any]:
    """Expenses of a month (by accrual date) with totals; generates due recurring expenses first."""
    if generate_recurring(db):
        db.commit()
    start, end = period_bounds(period)
    q = select(Expense).where(Expense.date >= start, Expense.date <= end)
    if status:
        q = q.where(Expense.status == status)
    if category_id:
        q = q.where(Expense.category_id == category_id)
    if kind:
        q = q.where(Expense.kind == kind)
    rows = list(db.scalars(q.order_by(Expense.date.desc(), Expense.id.desc())))
    cats, methods = _names(db)
    today = local_today()
    items = [serialize(e, cats, methods, today) for e in rows]
    total = sum(e.amount_cents for e in rows)
    by_cat: dict[int, dict[str, Any]] = {}
    for e in rows:
        row = by_cat.setdefault(e.category_id, {"category_id": e.category_id, "name": cats.get(e.category_id, "—"),
                                                 "count": 0, "total_cents": 0})
        row["count"] += 1
        row["total_cents"] += e.amount_cents
    categories = sorted(by_cat.values(), key=lambda r: -r["total_cents"])
    for r in categories:
        r["pct"] = round(r["total_cents"] * 100 / total, 1) if total else 0.0
    return {
        "period": period,
        "items": items,
        "totals": {
            "total_cents": total,
            "paid_cents": sum(e.amount_cents for e in rows if e.status == "paid"),
            "pending_cents": sum(e.amount_cents for e in rows if e.status == "pending"),
            "overdue_cents": sum(i["amount_cents"] for i in items if i["overdue"]),
            "fixed_cents": sum(e.amount_cents for e in rows if e.kind == "fixed"),
            "variable_cents": sum(e.amount_cents for e in rows if e.kind == "variable"),
            "count": len(rows),
        },
        "by_category": categories,
    }


# ---------------------------------------------------------------- recurring


def list_recurring(db: Session) -> list[dict[str, Any]]:
    cats, methods = _names(db)
    rows = db.scalars(select(RecurringExpense).order_by(RecurringExpense.active.desc(), RecurringExpense.day_of_month, RecurringExpense.id))
    return [
        {
            "id": r.id, "category_id": r.category_id, "category_name": cats.get(r.category_id, "—"),
            "description": r.description, "amount_cents": r.amount_cents, "day_of_month": r.day_of_month,
            "payment_method": r.payment_method, "payment_method_name": methods.get(r.payment_method or "", r.payment_method),
            "active": r.active, "start_period": r.start_period, "last_period": r.last_period, "notes": r.notes,
        }
        for r in rows
    ]


def create_recurring(db: Session, data: dict[str, Any], user: User) -> RecurringExpense:
    cat = _category(db, data["category_id"])
    description = data["description"].strip()
    if not description:
        raise HTTPException(400, "Escribí un concepto")
    r = RecurringExpense(
        category_id=cat.id,
        description=description,
        amount_cents=data["amount_cents"],
        day_of_month=data.get("day_of_month") or 10,
        payment_method=_method(db, data.get("payment_method")),
        start_period=parse_period(data.get("start_period")),
        notes=(data.get("notes") or "").strip() or None,
        user_id=user.id,
    )
    db.add(r)
    db.flush()
    audit.log(db, user.id, "create", "recurring_expense", r.id, {"amount_cents": r.amount_cents, "description": description})
    generate_recurring(db)
    db.commit()
    return r


def update_recurring(db: Session, recurring_id: int, changes: dict[str, Any], user: User) -> RecurringExpense:
    """Changes apply to the months generated from now on; already generated expenses keep their values."""
    r = db.get(RecurringExpense, recurring_id)
    if r is None:
        raise HTTPException(404, "Gasto fijo no encontrado")
    if changes.get("category_id") not in (None, r.category_id):
        _category(db, changes["category_id"])
    if "payment_method" in changes:
        r.payment_method = _method(db, changes.pop("payment_method"))
    if "notes" in changes:
        r.notes = (changes.pop("notes") or "").strip() or None
    for k, v in changes.items():
        if v is not None:
            setattr(r, k, v.strip() if isinstance(v, str) else v)
    audit.log(db, user.id, "update", "recurring_expense", r.id, {k: str(v) for k, v in changes.items()})
    if r.active:
        generate_recurring(db)
    db.commit()
    return r


def generate_recurring(db: Session, today: date | None = None) -> int:
    """Pending expense of every active monthly template for each month up to the current one that wasn't
    generated yet (`last_period`): a month deleted by hand is never generated again. Idempotent. Flushes,
    never commits."""
    current = period_of(today or local_today())
    floor = add_months(current, -(MAX_CATCH_UP_MONTHS - 1))
    made = 0
    for r in db.scalars(select(RecurringExpense).where(RecurringExpense.active.is_(True))):
        p = max(r.start_period, add_months(r.last_period, 1) if r.last_period else r.start_period, floor)
        if p > current:
            continue
        existing = set(db.scalars(select(Expense.period).where(Expense.recurring_id == r.id, Expense.period.is_not(None))))
        while p <= current:
            if p not in existing:
                due = due_date_in(p, r.day_of_month)
                db.add(Expense(category_id=r.category_id, kind="fixed", description=r.description, amount_cents=r.amount_cents,
                               date=due, due_date=due, status="pending", payment_method=r.payment_method,
                               recurring_id=r.id, period=p, user_id=r.user_id))
                made += 1
            p = add_months(p, 1)
        r.last_period = current
    if made:
        db.flush()
    return made


def job() -> None:
    """Periodic job (app/jobs.py): generates this month's fixed expenses even if nobody opens Gastos."""
    from app.db import SessionLocal

    with SessionLocal() as db:
        if generate_recurring(db):
            db.commit()


# ---------------------------------------------------------------- result ("ganancia real")


def losses(db: Session, a: datetime, b: datetime) -> dict[str, int]:
    """Waste (mermas, at their cost) and courtesies (ingredients given away) in [a, b) UTC."""
    cost = case((StockMovement.unit_cost_cents > 0, StockMovement.unit_cost_cents), else_=StockItem.avg_cost_cents)
    waste = db.scalar(
        select(func.coalesce(func.sum(StockMovement.qty * cost), 0))
        .join(StockItem, StockItem.id == StockMovement.stock_item_id)
        .where(StockMovement.type == "waste", StockMovement.ts >= a, StockMovement.ts < b)
    )
    courtesy = db.scalar(
        select(func.coalesce(func.sum(Sale.cost_cents), 0))
        .where(Sale.status == "completed", Sale.is_courtesy.is_(True), Sale.ts >= a, Sale.ts < b)
    )
    return {"waste_cents": int(round(abs(waste or 0))), "courtesy_cost_cents": int(courtesy or 0)}


def result(db: Session, start: date, end: date) -> dict[str, Any]:
    """Ventas − costo de mercadería − cortesías/mermas − gastos = ganancia real, for local days [start, end]."""
    a, b = range_bounds_utc(start, end)
    sales, cogs, tickets = db.execute(
        select(func.coalesce(func.sum(Sale.total_cents), 0), func.coalesce(func.sum(Sale.cost_cents), 0), func.count(Sale.id))
        .where(Sale.status == "completed", Sale.is_courtesy.is_(False), Sale.ts >= a, Sale.ts < b)
    ).one()
    lost = losses(db, a, b)
    exp_total, exp_pending = db.execute(
        select(func.coalesce(func.sum(Expense.amount_cents), 0),
               func.coalesce(func.sum(case((Expense.status == "pending", Expense.amount_cents), else_=0)), 0))
        .where(Expense.date >= start, Expense.date <= end)
    ).one()
    sales, cogs = int(sales), int(cogs)
    gross = sales - cogs
    loss = lost["waste_cents"] + lost["courtesy_cost_cents"]
    profit = gross - loss - int(exp_total)
    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "sales_cents": sales,
        "tickets": int(tickets),
        "cogs_cents": cogs,
        "gross_margin_cents": gross,
        "waste_cents": lost["waste_cents"],
        "courtesy_cost_cents": lost["courtesy_cost_cents"],
        "losses_cents": loss,
        "expenses_cents": int(exp_total),
        "expenses_pending_cents": int(exp_pending),
        "profit_cents": profit,
        "profit_pct": round(profit * 100 / sales, 1) if sales else None,
    }


def period_result(db: Session, period: str) -> dict[str, Any]:
    """Result of a month. The current month runs up to today (sales AND expenses dated until today), so it
    reads as "so far"; the expenses still to come this month are reported apart (`expenses_upcoming_cents`)."""
    start, end = period_bounds(period)
    today = local_today()
    partial = start <= today <= end
    res = result(db, start, min(end, today) if partial else end)
    res["expenses_upcoming_cents"] = 0
    if partial and today < end:
        res["expenses_upcoming_cents"] = int(db.scalar(
            select(func.coalesce(func.sum(Expense.amount_cents), 0)).where(Expense.date > today, Expense.date <= end)) or 0)
    res["period"] = period
    res["partial"] = partial
    return res


def month_result(db: Session, period: str) -> dict[str, Any]:
    """The month (so far) and the previous one, for the dashboard card."""
    if generate_recurring(db):
        db.commit()
    cur = period_result(db, period)
    prev = period_result(db, add_months(period, -1))
    return {"period": period, "partial": cur["partial"], "current": cur, "previous": prev}


def expenses_by_category(db: Session, start: date, end: date) -> dict[int, int]:
    return {cid: int(t or 0) for cid, t in db.execute(
        select(Expense.category_id, func.sum(Expense.amount_cents))
        .where(Expense.date >= start, Expense.date <= end).group_by(Expense.category_id)
    ).all()}


# ---------------------------------------------------------------- receipt photo


def _receipts_dir() -> Path:
    d = DATA_DIR / "receipts"  # NOT under /uploads (public static mount): served only to managers
    d.mkdir(parents=True, exist_ok=True)
    return d


def receipt_file(e: Expense) -> Path | None:
    if not e.receipt_path or not re.fullmatch(r"[0-9a-f]{32}\.webp", e.receipt_path):
        return None
    return _receipts_dir() / e.receipt_path


def save_receipt(db: Session, expense_id: int, raw: bytes, content_type: str | None, user: User) -> Expense:
    """Same pipeline as product photos (Pillow validates, fixes orientation, re-encodes WebP without metadata)."""
    from app.services.product_images import ALLOWED_TYPES, MAX_UPLOAD_BYTES, _encode, _open

    e = _get(db, expense_id)
    if (content_type or "").split(";")[0].strip().lower() not in ALLOWED_TYPES:
        raise HTTPException(415, "Formato no soportado: subí una foto JPG, PNG o WebP")
    if not raw:
        raise HTTPException(400, "El archivo está vacío")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "La foto pesa demasiado (máximo 8 MB)")
    data = _encode(_open(raw), 1600, 80)
    old = receipt_file(e)
    name = f"{secrets.token_hex(16)}.webp"
    (_receipts_dir() / name).write_bytes(data)
    e.receipt_path = name
    audit.log(db, user.id, "receipt", "expense", e.id, None)
    db.commit()
    if old is not None:
        old.unlink(missing_ok=True)
    return e


def delete_receipt(db: Session, expense_id: int, user: User) -> Expense:
    e = _get(db, expense_id)
    old = receipt_file(e)
    e.receipt_path = None
    audit.log(db, user.id, "delete_receipt", "expense", e.id, None)
    db.commit()
    if old is not None:
        old.unlink(missing_ok=True)
    return e


def receipt_path_for(db: Session, expense_id: int) -> Path:
    path = receipt_file(_get(db, expense_id))
    if path is None or not path.is_file():
        raise HTTPException(404, "Este gasto no tiene comprobante")
    return path


# ---------------------------------------------------------------- demo data


def seed_demo(db: Session, admin_id: int | None) -> None:
    """Fictional fixed and variable expenses for the last 3 months (paid) and this month (some pending)."""
    ensure_categories(db)
    cats = {c.name: c.id for c in db.scalars(select(ExpenseCategory))}
    today = local_today()
    cur = period_of(today)
    start = add_months(cur, -3)
    fixed = [
        ("Alquiler", "Alquiler del local", 150_000_000, 10, "transferencia"),
        ("Servicios (luz, gas, agua, internet)", "Luz", 25_000_000, 15, "debito"),
        ("Servicios (luz, gas, agua, internet)", "Internet y teléfono", 4_500_000, 8, "debito"),
        ("Sueldos y cargas sociales", "Sueldos del equipo", 520_000_000, 5, "transferencia"),
        ("Impuestos y tasas", "Monotributo e IIBB", 95_000_000, 20, "transferencia"),
        ("Abonos y suscripciones", "Música ambiental", 2_000_000, 1, "credito"),
    ]
    for cat, desc, amount, day, method in fixed:
        db.add(RecurringExpense(category_id=cats[cat], description=desc, amount_cents=amount, day_of_month=day,
                                payment_method=method, start_period=start, user_id=admin_id))
    db.flush()
    generate_recurring(db, today)
    for e in db.scalars(select(Expense).where(Expense.status == "pending", Expense.due_date < today)):
        e.status = "paid"
        e.paid_at = to_utc_naive(datetime.combine(e.due_date, datetime.min.time()).replace(hour=11))
    variable = [
        (40, "Mantenimiento y reparaciones", "Service de la máquina de espresso", 18_000_000, "transferencia"),
        (25, "Limpieza y descartables", "Artículos de limpieza", 3_500_000, "efectivo"),
        (12, "Publicidad", "Volantes del barrio", 2_500_000, "efectivo"),
        (3, "Comisiones y gastos bancarios", "Comisiones del posnet", 6_000_000, "debito"),
    ]
    for days_ago, cat, desc, amount, method in variable:
        d = date.fromordinal(today.toordinal() - days_ago)
        db.add(Expense(category_id=cats[cat], kind="variable", description=desc, amount_cents=amount, date=d, status="paid",
                       paid_at=to_utc_naive(datetime.combine(d, datetime.min.time()).replace(hour=12)),
                       payment_method=method, user_id=admin_id))
    db.flush()
