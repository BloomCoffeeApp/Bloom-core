from typing import Any

from sqlalchemy.orm import Session

from app.models import Setting

DEFAULTS: dict[str, Any] = {
    "business": {"name": "Mi Cafetería", "cuit": "", "address": "", "phone": "", "ticket_footer": "¡Gracias por tu visita!"},
    "currency": "ARS",
    "lock_minutes": 10,
    "loyalty": {"enabled": True, "pesos_per_point": 1000, "points_per_reward": 100, "reward_value_cents": 500000},
    "alerts": {"expiry_days": 5, "supplier_due_days": 3, "roast_max_days": 30, "roast_min_days": 5},
    "backup": {"enabled": True, "keep": 30},
    "network": {"lan_enabled": False},
    "public_menu": {"enabled": True, "show_prices": True, "message": ""},
    # Order screen (bar/kitchen): which POS channels send their sales and the target minutes of each.
    "orders": {
        "enabled": True,
        "channels": {"salon": True, "llevar": True, "delivery": True},
        "targets": {"salon": 8, "llevar": 5, "delivery": 15},
        "warn_pct": 75,
    },
    # Customers ordering from their table (Pro, `public_menu`): limits against abuse.
    "table_ordering": {
        "enabled": False,
        "max_items": 20,
        "orders_per_10min": 3,
        "max_pending": 3,
        "call_minutes": 10,
    },
    # Free plan "Elegí tus activos" (services/free_plan.py); only changed through /api/free-plan.
    "free_actives": {},
    "setup_done": False,
}


def get(db: Session, key: str) -> Any:
    row = db.get(Setting, key)
    if row is None:
        return DEFAULTS.get(key)
    default = DEFAULTS.get(key)
    if isinstance(default, dict) and isinstance(row.value, dict):
        return {**default, **row.value}
    return row.value


def put(db: Session, key: str, value: Any) -> None:
    row = db.get(Setting, key)
    if row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value


def get_all(db: Session) -> dict[str, Any]:
    return {k: get(db, k) for k in DEFAULTS}
