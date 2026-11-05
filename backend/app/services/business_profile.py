"""Business types ("perfiles"): which modules/sections the app shows.

A profile is a set of sensible defaults (take away, small café, café with tables, delivery only…);
the owner can then turn single modules on/off (overrides). This is about simplicity, not licensing:
Pro gating still applies on top, and hiding a module never deletes its data (it's UI-level, plus
the order screen stops receiving POS sales while it's hidden so it doesn't pile up stale orders).

Stored in the `business_profile` setting as ``{"profile": key, "modules": {module: bool}}`` where
``modules`` only keeps the differences from the profile's defaults. Installations that never chose
a profile behave as ``salon`` (everything on), so upgrading changes nothing.

Adding a profile (panadería, heladería…) = one entry in PROFILES (+ its icon in the front).
"""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.services import settings

SETTING = "business_profile"
DEFAULT_PROFILE = "salon"


@dataclass(frozen=True)
class Module:
    key: str
    label: str
    description: str
    group: str  # venta | operacion | gestion | clientes
    feature: str | None = None  # Pro license feature that also gates it (informative)
    requires: tuple[str, ...] = ()


MODULES: tuple[Module, ...] = (
    Module("dine_in", "Consumo en el local", "Canal «Salón» en el punto de venta.", "venta"),
    Module("takeaway", "Para llevar", "Canal «Para llevar» en el punto de venta.", "venta"),
    Module("delivery", "Delivery", "Canal «Delivery» en el punto de venta.", "venta"),
    Module("tables", "Mesas", "Número de mesa, mesas abiertas y pedidos con QR desde la mesa.", "venta",
           "public_menu", ("dine_in",)),
    Module("orders", "Pantalla de pedidos", "Pedidos para la barra o la cocina, con tiempos y avisos.", "operacion"),
    Module("stations", "Estaciones y pantalla de retiro", "Barra y cocina por separado y números en la TV.",
           "operacion", "orders_pro", ("orders",)),
    Module("barista", "Barista", "Recetas de bebidas, guía y calibración del café.", "operacion", "barista"),
    Module("stock", "Stock e insumos", "Insumos, movimientos, conteos y mermas.", "gestion"),
    Module("purchases", "Compras", "Proveedores, órdenes de compra y cuenta corriente.", "gestion", "purchases"),
    Module("reports", "Reportes", "Reportes avanzados y exportación.", "gestion", "reports"),
    Module("customers", "Clientes", "Fichas de clientes y cuenta corriente.", "clientes"),
    Module("loyalty", "Fidelización", "Puntos y tarjeta de sellos.", "clientes", None, ("customers",)),
    Module("promos", "Promos", "Combos y descuentos programados.", "clientes", "promos"),
    Module("public_menu", "Menú para clientes", "Menú en el celular por QR y en la pantalla del local.", "clientes",
           "public_menu"),
)
MODULE_KEYS = tuple(m.key for m in MODULES)
_BY_KEY = {m.key: m for m in MODULES}
# A sale needs a channel: at least one of these always stays on.
CHANNEL_MODULES = ("dine_in", "takeaway", "delivery")


@dataclass(frozen=True)
class Profile:
    key: str
    label: str
    description: str
    off: frozenset[str] = field(default_factory=frozenset)  # everything else is on

    def defaults(self) -> dict[str, bool]:
        return {k: k not in self.off for k in MODULE_KEYS}


PROFILES: tuple[Profile, ...] = (
    Profile("takeaway", "Take away / al paso", "Mostrador, sin mesas: se pide, se paga y se lleva.",
            frozenset({"dine_in", "delivery", "tables", "stations", "purchases"})),
    Profile("small", "Cafetería chica", "Pocas mesas, sin mozos: se pide y se paga en el mostrador.",
            frozenset({"delivery", "tables", "orders", "stations", "purchases", "promos"})),
    Profile("salon", "Cafetería con salón", "Mesas con mozo, barra y cocina: todos los módulos.", frozenset()),
    Profile("delivery", "Solo pedidos / delivery", "Sin atención al público: pedidos para llevar y envíos.",
            frozenset({"dine_in", "tables", "barista", "loyalty", "public_menu"})),
)
PROFILE_KEYS = tuple(p.key for p in PROFILES)
_PROFILES = {p.key: p for p in PROFILES}


class ProfileError(ValueError):
    pass


def _resolve(profile: str, overrides: dict[str, bool]) -> dict[str, bool]:
    mods = _PROFILES[profile].defaults()
    mods.update({k: bool(v) for k, v in overrides.items() if k in mods})
    # A module whose requirement is off is off too (e.g. no tables without dine-in).
    changed = True
    while changed:
        changed = False
        for m in MODULES:
            if mods[m.key] and any(not mods[r] for r in m.requires):
                mods[m.key] = False
                changed = True
    return mods


def _stored(db: Session) -> tuple[str, dict[str, bool]]:
    raw = settings.get(db, SETTING) or {}
    profile = raw.get("profile") if raw.get("profile") in _PROFILES else DEFAULT_PROFILE
    mods = raw.get("modules") if isinstance(raw.get("modules"), dict) else {}
    return profile, {k: bool(v) for k, v in mods.items() if k in _BY_KEY}


def effective(db: Session) -> dict[str, bool]:
    profile, overrides = _stored(db)
    return _resolve(profile, overrides)


def is_enabled(db: Session, module: str) -> bool:
    return effective(db).get(module, True)


def normalize(profile: str, modules: dict[str, Any] | None) -> tuple[str, dict[str, bool]]:
    """Validates a choice and returns (profile, overrides that differ from the profile defaults)."""
    if profile not in _PROFILES:
        raise ProfileError("Tipo de negocio inexistente")
    modules = modules or {}
    unknown = set(modules) - set(MODULE_KEYS)
    if unknown:
        raise ProfileError(f"Módulo inexistente: {', '.join(sorted(unknown))}")
    eff = _resolve(profile, {k: bool(v) for k, v in modules.items()})
    if not any(eff[c] for c in CHANNEL_MODULES):
        raise ProfileError("Dejá al menos un canal de venta (salón, para llevar o delivery).")
    defaults = _PROFILES[profile].defaults()
    return profile, {k: v for k, v in eff.items() if v != defaults[k]}


def save(db: Session, profile: str, modules: dict[str, Any] | None) -> None:
    profile, overrides = normalize(profile, modules)
    settings.put(db, SETTING, {"profile": profile, "modules": overrides})
    db.flush()  # a new settings row is pending: make the next read (db.get) see it


def set_module(db: Session, module: str, enabled: bool) -> None:
    """Turns one module on/off keeping the current profile (the hidden-page "Activarlo")."""
    if module not in _BY_KEY:
        raise ProfileError("Módulo inexistente")
    profile = _stored(db)[0]
    mods = effective(db)
    mods[module] = enabled
    if enabled:  # also turn on what it needs
        for r in _BY_KEY[module].requires:
            mods[r] = True
    save(db, profile, mods)


def info(db: Session) -> dict[str, Any]:
    return info_for(*_stored(db))


def info_for(profile: str, overrides: dict[str, bool]) -> dict[str, Any]:
    return {
        "profile": profile,
        "overrides": overrides,
        "modules": _resolve(profile, overrides),
        "catalog": [
            {"key": m.key, "label": m.label, "description": m.description, "group": m.group,
             "feature": m.feature, "requires": list(m.requires)}
            for m in MODULES
        ],
        "profiles": [
            {"key": p.key, "label": p.label, "description": p.description, "modules": p.defaults()}
            for p in PROFILES
        ],
    }
