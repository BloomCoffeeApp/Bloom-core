"""Permission catalog and the built-in roles.

Every endpoint that used to check a fixed role list now asks for a permission
(`app.auth.require_permission`). The built-in roles map to the exact sets they had before,
so nothing changes until the owner edits a role or creates a custom one (services/roles.py).

`admin` is not a set of permissions: it always passes every check and can't be edited.
Some things stay with the admin role only, on purpose (license, Bloom account, the roles editor):
they decide who controls the business and can't be delegated.
"""

ADMIN = "admin"

# key -> (group, label, description). Order = order in the roles editor.
PERMISSIONS: dict[str, tuple[str, str, str]] = {
    # Punto de venta y caja
    "pos.sell": ("Ventas y caja", "Vender en el POS", "Cobrar, ver ventas, cuentas abiertas e imprimir tickets"),
    "pos.discount": ("Ventas y caja", "Aplicar descuentos", "Descuentos por línea o sobre el total"),
    "pos.courtesy": ("Ventas y caja", "Registrar cortesías", "Ventas sin cargo (quedan auditadas)"),
    "sales.void": ("Ventas y caja", "Anular ventas", "Anula la venta y devuelve el stock"),
    "cash.open_close": ("Ventas y caja", "Abrir y cerrar caja", "Apertura, cierre, arqueos e historial de caja"),
    "cash.movements": ("Ventas y caja", "Ingresos y retiros de caja", "Movimientos de efectivo durante el turno"),
    # Catálogo y stock
    "catalog.edit": ("Productos y stock", "Editar productos", "Productos, categorías, tamaños, modificadores, fotos y precios"),
    "prices.edit": ("Productos y stock", "Aumento masivo de precios", "Cambiar precios de muchos productos a la vez"),
    "stock.view": ("Productos y stock", "Ver stock", "Insumos, movimientos, conteos y sugerencias de compra"),
    "stock.edit": ("Productos y stock", "Editar insumos", "Alta, baja y edición de insumos y sus categorías"),
    "stock.adjust": ("Productos y stock", "Ajustes, mermas y conteos", "Corregir existencias (queda registrado)"),
    "purchases.manage": ("Productos y stock", "Compras y proveedores", "Órdenes, recepciones, proveedores y pagos"),
    # Clientes
    "customers.edit": ("Clientes", "Clientes", "Ver, crear y editar clientes; cobrar cuenta corriente"),
    "customers.manage": ("Clientes", "Gestión de clientes", "Archivar, límite de cuenta corriente y ajuste de puntos"),
    "promos.manage": ("Clientes", "Promos y fidelidad", "Combos, descuentos programados y tarjetas de sellos"),
    # Operación
    "orders.manage": ("Operación", "Configurar pedidos", "Pantalla de pedidos, estaciones y mesas"),
    "notices.manage": ("Operación", "Avisos y checklists", "Crear y editar avisos y checklists"),
    "barista.use": ("Operación", "Módulo barista", "Cafés, recetas, extracciones, mantenimiento y guías"),
    "barista.manage": ("Operación", "Gestión del barista", "Editar guías de bebidas y registros de otros"),
    # Gestión
    "reports.view": ("Gestión", "Reportes y costos", "Reportes, márgenes y costos en el inicio"),
    "expenses.manage": ("Gestión", "Gastos", "Cargar y pagar gastos (alquiler, servicios, sueldos…) y ver la ganancia real"),
    "staff.manage": ("Gestión", "Empleados", "Fichas, fichajes, horas, sueldos y adelantos"),
    "settings.manage": ("Administración", "Configuración del negocio", "Datos del negocio, medios de pago, impresoras, red y menú"),
    "users.manage": ("Administración", "Usuarios", "Crear usuarios y cambiar PIN (solo con roles que no superen los propios)"),
    "system.manage": ("Administración", "Respaldos y sistema", "Respaldos, restauración, actualizaciones y registro de auditoría"),
}

ALL = frozenset(PERMISSIONS)

_SELL = {"pos.sell", "pos.courtesy", "cash.open_close", "cash.movements", "customers.edit"}
_MANAGE = {
    "pos.discount", "sales.void", "catalog.edit", "prices.edit", "stock.view", "stock.edit", "stock.adjust",
    "purchases.manage", "customers.manage", "promos.manage", "orders.manage", "notices.manage",
    "barista.use", "barista.manage", "reports.view", "expenses.manage",
}

# Built-in roles: name, short description and default permissions (= behavior before roles were editable).
BUILTIN_ROLES: dict[str, dict] = {
    ADMIN: {"name": "Administrador", "hint": "Acceso total, configuración y respaldos", "permissions": ALL},
    "encargado": {"name": "Encargado", "hint": "Gestión: stock, compras, reportes, productos",
                  "permissions": frozenset(_SELL | _MANAGE)},
    "cajero": {"name": "Cajero", "hint": "Punto de venta, caja y clientes", "permissions": frozenset(_SELL)},
    "barista": {"name": "Barista", "hint": "Módulo barista y stock", "permissions": frozenset({"barista.use", "stock.view"})},
}

# Permissions that only make sense with something else (the editor adds the requirement automatically).
REQUIRES: dict[str, str] = {
    "pos.discount": "pos.sell",
    "pos.courtesy": "pos.sell",
    "sales.void": "pos.sell",
    "stock.edit": "stock.view",
    "stock.adjust": "stock.view",
    "customers.manage": "customers.edit",
    "barista.manage": "barista.use",
}


def normalize(perms: set[str] | frozenset[str] | list[str]) -> frozenset[str]:
    """Known permissions only, plus whatever they require."""
    out = {p for p in perms if p in PERMISSIONS}
    for p in list(out):
        if (req := REQUIRES.get(p)) is not None:
            out.add(req)
    return frozenset(out)
