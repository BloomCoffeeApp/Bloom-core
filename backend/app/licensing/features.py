"""What Pro unlocks, and the guard used by API routes."""

from fastapi import HTTPException, status

from app.config import APP_DISPLAY_NAME
from app.licensing.status import current_status

PRO_LABEL = f"{APP_DISPLAY_NAME} Pro"

# Pro modules (their code ships only in the Pro edition) and Pro capabilities of the core.
PRO_FEATURES: dict[str, str] = {
    "barista": "Asistente de barista y guía de bebidas",
    "purchases": "Compras, proveedores y cuenta corriente",
    "reports": "Reportes avanzados y exportación a Excel/CSV",
    "public_menu": "Menú para clientes (QR y pantalla)",
    "lan": "Modo red local (tablets y otras PCs)",
    "users": "Usuarios ilimitados",
    "backup_export": "Descargar y restaurar respaldos",
    "orders_pro": "Pedidos avanzados (estaciones, tiempos por producto, pantalla de retiro)",
    "loyalty_pro": "Fidelidad por compras (tarjeta de sellos)",
    "promos": "Promociones: combos y descuentos programados",
}

# Free plan caps. The vendor can change them without a new .exe through the signed remote config
# ("free_limits"); these built-in values apply offline or before the first config arrives.
FREE_LIMITS_DEFAULT: dict[str, int] = {
    "products": 5, "users": 1, "customers": 20, "stock_items": 15, "sales_history_days": 30,
    # Days between two swaps in "Elegí tus activos" (services/free_plan.py); 0 = no wait.
    "swap_cooldown_days": 7,
}
# Keys that may be 0 (the rest must be >= 1).
FREE_LIMITS_ZERO_OK = {"swap_cooldown_days"}
FREE_LIMIT_LABELS = {"products": "productos", "users": "usuarios activos", "customers": "clientes", "stock_items": "insumos"}
FREE_LIMIT_LABELS_ONE = {"products": "producto", "users": "usuario activo", "customers": "cliente", "stock_items": "insumo"}


def free_limits() -> dict[str, int]:
    from app import remote_config

    limits = dict(FREE_LIMITS_DEFAULT)
    for key, value in remote_config.free_limits().items():
        if key in limits and isinstance(value, int) and not isinstance(value, bool) and value >= (0 if key in FREE_LIMITS_ZERO_OK else 1):
            limits[key] = value
    return limits


def check_free_limit(kind: str, current: int) -> None:
    """Raises 402 when the free plan already has `current` >= its cap (Pro and trials: no caps)."""
    if current_status().valid:
        return
    limit = free_limits()[kind]
    if current >= limit:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"El plan gratuito permite hasta {limit} "
            f"{(FREE_LIMIT_LABELS_ONE if limit == 1 else FREE_LIMIT_LABELS)[kind]}. Con {PRO_LABEL} no hay límite.",
        )


def has_feature(feature: str) -> bool:
    return current_status().has(feature)


def require_feature(feature: str):
    """Route dependency: 402 with an explanation when the feature isn't licensed."""

    def _dep() -> None:
        if not has_feature(feature):
            label = PRO_FEATURES.get(feature, feature)
            raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, f"{label} es parte de {PRO_LABEL}.")

    return _dep

