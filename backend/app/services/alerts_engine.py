"""Alert rules engine.

`evaluate(db)` runs every rule, upserts one Alert per condition (keyed by the UNIQUE
`dedupe_key`) and auto-resolves open/read alerts whose condition no longer holds.
It never commits: the caller (jobs.py / the refresh endpoint) does.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Alert,
    CashSession,
    Coffee,
    Customer,
    Equipment,
    Expense,
    MaintenanceTask,
    Purchase,
    StockItem,
    StockLot,
    Supplier,
    User,
    utcnow,
)
from app.services import settings as settings_svc
from app.services.timeutil import local_today, to_local

SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2}


@dataclass
class Spec:
    key: str
    type: str
    severity: str
    title: str
    message: str
    link: str | None = None
    entity: str | None = None
    entity_id: int | None = None


def _fmt_qty(q: float, unit: str) -> str:
    return f"{q:g} {unit}"


def _fmt_money(cents: int) -> str:
    s = f"{cents / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"$ {s}"


def _days(n: int) -> str:
    return "1 día" if abs(n) == 1 else f"{abs(n)} días"


# ---------------------------------------------------------------- rules


def rule_stock(db: Session, cfg: dict[str, Any]) -> list[Spec]:
    out: list[Spec] = []
    items = db.scalars(select(StockItem).where(StockItem.active.is_(True)))
    for it in items:
        if it.current_qty <= 0 and (it.min_qty > 0 or it.current_qty < 0):
            out.append(Spec(
                key=f"stock_out:{it.id}", type="stock_out", severity="critical",
                title=f"Sin stock: {it.name}",
                message=f"Quedan {_fmt_qty(it.current_qty, it.unit)} (mínimo {_fmt_qty(it.min_qty, it.unit)}).",
                link="/stock", entity="stock_item", entity_id=it.id,
            ))
        elif it.min_qty > 0 and it.current_qty <= it.min_qty:
            out.append(Spec(
                key=f"stock_low:{it.id}", type="stock_low", severity="warning",
                title=f"Stock bajo: {it.name}",
                message=f"Quedan {_fmt_qty(it.current_qty, it.unit)} (mínimo {_fmt_qty(it.min_qty, it.unit)}).",
                link="/stock", entity="stock_item", entity_id=it.id,
            ))
    return out


def rule_lot_expiry(db: Session, cfg: dict[str, Any]) -> list[Spec]:
    today = local_today()
    limit = today + timedelta(days=int(cfg.get("expiry_days", 5)))
    rows = db.execute(
        select(StockLot, StockItem)
        .join(StockItem, StockItem.id == StockLot.stock_item_id)
        .where(StockLot.qty_remaining > 0, StockLot.expiry_date.is_not(None), StockLot.expiry_date <= limit)
    ).all()
    out: list[Spec] = []
    for lot, item in rows:
        days = (lot.expiry_date - today).days
        if days < 0:
            sev, when = "critical", f"venció hace {_days(days)}"
        elif days == 0:
            sev, when = "critical", "vence hoy"
        else:
            sev, when = "warning", f"vence en {_days(days)}"
        out.append(Spec(
            key=f"lot_expiry:{lot.id}", type="lot_expiry", severity=sev,
            title=f"Lote de {item.name} {when}",
            message=f"{_fmt_qty(lot.qty_remaining, item.unit)} con vencimiento {lot.expiry_date:%d/%m/%Y}.",
            link="/stock", entity="stock_lot", entity_id=lot.id,
        ))
    return out


def rule_supplier_due(db: Session, cfg: dict[str, Any]) -> list[Spec]:
    today = local_today()
    limit = today + timedelta(days=int(cfg.get("supplier_due_days", 3)))
    rows = db.execute(
        select(Purchase, Supplier.name)
        .join(Supplier, Supplier.id == Purchase.supplier_id)
        .where(Purchase.status != "paid", Purchase.due_date.is_not(None), Purchase.due_date <= limit)
    ).all()
    out: list[Spec] = []
    for p, supplier in rows:
        pending = max(p.total_cents - p.paid_cents, 0)
        if pending <= 0:
            continue
        days = (p.due_date - today).days
        if days < 0:
            sev, when = "critical", f"vencida hace {_days(days)}"
        elif days == 0:
            sev, when = "critical", "vence hoy"
        else:
            sev, when = "warning", f"vence en {_days(days)}"
        inv = f" {p.invoice_number}" if p.invoice_number else ""
        out.append(Spec(
            key=f"purchase_due:{p.id}", type="purchase_due", severity=sev,
            title=f"Factura{inv} de {supplier} {when}",
            message=f"Saldo pendiente {_fmt_money(pending)} — vencimiento {p.due_date:%d/%m/%Y}.",
            link="/compras", entity="purchase", entity_id=p.id,
        ))
    return out


def rule_cash_stale(db: Session, cfg: dict[str, Any]) -> list[Spec]:
    today = local_today()
    out: list[Spec] = []
    for s in db.scalars(select(CashSession).where(CashSession.status == "open")):
        opened = to_local(s.opened_at)
        if opened.date() >= today:
            continue
        who = db.get(User, s.opened_by)
        out.append(Spec(
            key=f"cash_stale:{s.id}", type="cash_stale", severity="critical",
            title="Caja abierta desde un día anterior",
            message=f"La caja abierta el {opened:%d/%m/%Y a las %H:%M}"
                    f"{f' por {who.name}' if who else ''} sigue sin cerrarse.",
            link="/caja", entity="cash_session", entity_id=s.id,
        ))
    return out


def rule_birthdays(db: Session, cfg: dict[str, Any]) -> list[Spec]:
    from app.services.customers import birthdays_today

    today = local_today()
    return [
        Spec(
            key=f"birthday:{c.id}:{today.isoformat()}", type="birthday", severity="info",
            title=f"Hoy cumple años {c.name}",
            message="¡Saludalo y ofrecele un mimo de la casa!" + (f" Tel: {c.phone}" if c.phone else ""),
            link=f"/clientes/{c.id}", entity="customer", entity_id=c.id,
        )
        for c in birthdays_today(db)
    ]


def rule_roast(db: Session, cfg: dict[str, Any]) -> list[Spec]:
    today = local_today()
    max_days = int(cfg.get("roast_max_days", 30))
    out: list[Spec] = []
    for c in db.scalars(select(Coffee).where(Coffee.active.is_(True), Coffee.roast_date.is_not(None))):
        days = (today - c.roast_date).days
        if days > max_days:
            out.append(Spec(
                key=f"roast_old:{c.id}", type="roast_old", severity="warning",
                title=f"Café pasado de tueste: {c.name}",
                message=f"Tiene {_days(days)} desde el tueste (máximo recomendado {max_days}).",
                link="/barista/cafes", entity="coffee", entity_id=c.id,
            ))
    return out


def rule_maintenance(db: Session, cfg: dict[str, Any]) -> list[Spec]:
    now = utcnow()
    rows = db.execute(
        select(MaintenanceTask, Equipment)
        .join(Equipment, Equipment.id == MaintenanceTask.equipment_id)
        .where(Equipment.active.is_(True))
    ).all()
    out: list[Spec] = []
    for task, eq in rows:
        reasons: list[str] = []
        if task.every_days:
            ref = task.last_done_at or eq.created_at
            elapsed = (now - ref).days if ref else 0
            if elapsed >= task.every_days:
                reasons.append(f"pasaron {_days(elapsed)} (cada {task.every_days})")
        if task.every_shots:
            shots = eq.shot_counter - (task.last_done_shots or 0)
            if shots >= task.every_shots:
                reasons.append(f"{shots} shots desde el último (cada {task.every_shots})")
        if reasons:
            out.append(Spec(
                key=f"maintenance:{task.id}", type="maintenance", severity="warning",
                title=f"Mantenimiento pendiente: {task.name} — {eq.name}",
                message="Toca hacerlo: " + "; ".join(reasons) + ".",
                link="/barista/equipos", entity="maintenance_task", entity_id=task.id,
            ))
    return out


def rule_customer_debt(db: Session, cfg: dict[str, Any]) -> list[Spec]:
    rows = db.scalars(
        select(Customer).where(
            Customer.active.is_(True),
            Customer.balance_cents > 0,
            Customer.balance_cents > Customer.credit_limit_cents,
        )
    )
    return [
        Spec(
            key=f"debt_over_limit:{c.id}", type="debt_over_limit", severity="warning",
            title=f"{c.name} superó su límite de cuenta corriente",
            message=f"Debe {_fmt_money(c.balance_cents)} (límite {_fmt_money(c.credit_limit_cents)}).",
            link=f"/clientes/{c.id}", entity="customer", entity_id=c.id,
        )
        for c in rows
    ]


def rule_expense_due(db: Session, cfg: dict[str, Any]) -> list[Spec]:
    """Pending business expenses (Gastos) due soon or overdue."""
    today = local_today()
    limit = today + timedelta(days=int(cfg.get("expense_due_days", 3)))
    out: list[Spec] = []
    for e in db.scalars(select(Expense).where(Expense.status == "pending", Expense.due_date.is_not(None), Expense.due_date <= limit)):
        days = (e.due_date - today).days
        if days < 0:
            sev, when = "critical", f"venció hace {_days(days)}"
        elif days == 0:
            sev, when = "critical", "vence hoy"
        else:
            sev, when = "warning", f"vence en {_days(days)}"
        out.append(Spec(
            key=f"expense_due:{e.id}", type="expense_due", severity=sev,
            title=f"Gasto {when}: {e.description}",
            message=f"{_fmt_money(e.amount_cents)} — vencimiento {e.due_date:%d/%m/%Y}. Marcalo como pagado en Gastos.",
            link="/gastos", entity="expense", entity_id=e.id,
        ))
    return out


RULES: dict[str, Callable[[Session, dict[str, Any]], list[Spec]]] = {
    "stock": rule_stock,
    "lot_expiry": rule_lot_expiry,
    "supplier_due": rule_supplier_due,
    "cash_stale": rule_cash_stale,
    "birthday": rule_birthdays,
    "roast": rule_roast,
    "maintenance": rule_maintenance,
    "customer_debt": rule_customer_debt,
    "expense_due": rule_expense_due,
}

# Alert types owned by the engine (only these get auto-resolved).
ENGINE_TYPES = {
    "stock_low", "stock_out", "lot_expiry", "purchase_due", "cash_stale",
    "birthday", "roast_old", "maintenance", "debt_over_limit", "expense_due",
}

# Alert type -> permission needed to see it (amounts like salaries are for managers only).
PERMISSION_TYPES: dict[str, str] = {"expense_due": "expenses.manage"}


def register_rule(key: str, fn: Callable[[Session, dict[str, Any]], list[Spec]], types: set[str],
                  permission: str | None = None) -> None:
    """Extension point for Pro modules: adds a rule, the alert types it owns (they get auto-resolved when the
    condition clears) and, optionally, the permission a user needs to see those alerts. Idempotent."""
    RULES[key] = fn
    ENGINE_TYPES.update(types)
    if permission:
        PERMISSION_TYPES.update({t: permission for t in types})


# ---------------------------------------------------------------- engine


def collect(db: Session) -> dict[str, Spec]:
    cfg = settings_svc.get(db, "alerts") or {}
    specs: dict[str, Spec] = {}
    for rule in RULES.values():
        for spec in rule(db, cfg):
            specs[spec.key] = spec
    return specs


def _apply(alert: Alert, spec: Spec) -> None:
    escalated = SEVERITY_RANK.get(spec.severity, 2) < SEVERITY_RANK.get(alert.severity, 2)
    alert.type = spec.type
    alert.severity = spec.severity
    alert.title = spec.title[:160]
    alert.message = spec.message
    alert.link = spec.link
    alert.entity = spec.entity
    alert.entity_id = spec.entity_id
    if escalated and alert.status == "read":
        alert.status = "open"


ARCHIVE_SEP = "#"


def evaluate(db: Session) -> dict[str, int]:
    """Idempotent: creates new alerts, refreshes existing ones and resolves stale ones.

    While a condition holds, its alert lives under the plain dedupe_key (so it is never
    duplicated, and a manual "resolver" sticks). When the condition clears, the alert is
    resolved and its key archived as "<key>#<id>", so if the condition returns later a
    brand-new alert is raised.
    """
    specs = collect(db)
    existing = {a.dedupe_key: a for a in db.scalars(select(Alert))}
    now = utcnow()
    created = resolved = 0
    for key, spec in specs.items():
        alert = existing.get(key)
        if alert is None:
            alert = Alert(dedupe_key=key, status="open", created_at=now)
            _apply(alert, spec)
            db.add(alert)
            created += 1
        elif alert.status != "resolved":
            _apply(alert, spec)
    for key, alert in existing.items():
        if key in specs or ARCHIVE_SEP in key or alert.type not in ENGINE_TYPES:
            continue
        if alert.status != "resolved":
            alert.status = "resolved"
            alert.resolved_at = now
            resolved += 1
        alert.dedupe_key = f"{key}{ARCHIVE_SEP}{alert.id}"[:120]
    db.flush()
    return {"created": created, "resolved": resolved}
