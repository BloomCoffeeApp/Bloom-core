"""What Pro unlocks, and the guard used by API routes."""

from fastapi import HTTPException, status

from app.config import APP_DISPLAY_NAME
from app.licensing.status import current_status

PRO_LABEL = f"{APP_DISPLAY_NAME} Pro"

# Pro modules (their code ships only in the Pro edition) and Pro capabilities of the core.
PRO_FEATURES: dict[str, str] = {
    "barista": "Asistente de barista y guía de bebidas",
    "purchases": "Compras, proveedores y cuenta corriente",
    "reports": "Reportes avanzados",
    "exports": "Exportar a Excel y CSV",
    "public_menu": "Menú para clientes (QR y pantalla)",
    "lan": "Modo red local (tablets y otras PCs)",
    "users": "Usuarios ilimitados",
    "backup_export": "Descargar y restaurar respaldos",
}

FREE_MAX_USERS = 2


def has_feature(feature: str) -> bool:
    return current_status().has(feature)


def require_feature(feature: str):
    """Route dependency: 402 with an explanation when the feature isn't licensed."""

    def _dep() -> None:
        if not has_feature(feature):
            label = PRO_FEATURES.get(feature, feature)
            raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, f"{label} es parte de {PRO_LABEL}.")

    return _dep

