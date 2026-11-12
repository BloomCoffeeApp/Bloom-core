from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, utcnow

BREW_METHODS = ("espresso", "v60", "chemex", "aeropress", "french_press", "cold_brew", "moka")


class Coffee(IdMixin, TimestampMixin, Base):
    __tablename__ = "coffees"
    name: Mapped[str] = mapped_column(String(120))
    roaster: Mapped[str | None] = mapped_column(String(120))
    origin: Mapped[str | None] = mapped_column(String(120))
    variety: Mapped[str | None] = mapped_column(String(120))
    process: Mapped[str | None] = mapped_column(String(60))
    altitude_m: Mapped[int | None]
    roast_level: Mapped[str | None] = mapped_column(String(30))
    roast_date: Mapped[date | None] = mapped_column(Date)
    tasting_notes: Mapped[str | None] = mapped_column(Text)
    stock_item_id: Mapped[int | None] = mapped_column(ForeignKey("stock_items.id"))
    active: Mapped[bool] = mapped_column(default=True)
    # Tasting profile ("perfil"): expected notes (keys of the flavor wheel), roast point
    # (light..dark scale key) and expected 1..5 values {body, aroma, sweetness, bitterness, acidity}.
    flavor_notes: Mapped[list[str] | None] = mapped_column(JSON)
    roast_point: Mapped[str | None] = mapped_column(String(20))
    taste_profile: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    # Shown to customers as the coffee in use: house | decaf | origin (None = not on the menu).
    menu_role: Mapped[str | None] = mapped_column(String(10))


class Equipment(IdMixin, TimestampMixin, Base):
    __tablename__ = "equipment"
    kind: Mapped[str] = mapped_column(String(10))  # machine|grinder|other
    name: Mapped[str] = mapped_column(String(120))
    brand: Mapped[str | None] = mapped_column(String(60))
    model: Mapped[str | None] = mapped_column(String(60))
    grind_scale: Mapped[str | None] = mapped_column(String(60))  # e.g. "1-40 numérico", "stepless"
    shot_counter: Mapped[int] = mapped_column(default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(default=True)


class MaintenanceTask(IdMixin, Base):
    __tablename__ = "maintenance_tasks"
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    every_days: Mapped[int | None]
    every_shots: Mapped[int | None]
    last_done_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_done_shots: Mapped[int] = mapped_column(default=0)


class BrewRecipe(IdMixin, TimestampMixin, Base):
    __tablename__ = "brew_recipes"
    coffee_id: Mapped[int | None] = mapped_column(ForeignKey("coffees.id", ondelete="SET NULL"))
    method: Mapped[str] = mapped_column(String(20), default="espresso")
    name: Mapped[str] = mapped_column(String(120))
    dose_g: Mapped[float] = mapped_column(Float)
    yield_g: Mapped[float] = mapped_column(Float)
    time_min_s: Mapped[int | None]
    time_max_s: Mapped[int | None]
    temp_c: Mapped[float | None] = mapped_column(Float)
    pressure_bar: Mapped[float | None] = mapped_column(Float)
    preinfusion_s: Mapped[int | None]
    grind_ref: Mapped[str | None] = mapped_column(String(40))
    # [{"label": "Bloom", "start_s": 0, "end_s": 45, "target_g": 40}, ...]
    steps: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(Text)
    is_current: Mapped[bool] = mapped_column(default=False)


class ShotLog(IdMixin, Base):
    __tablename__ = "shot_logs"
    coffee_id: Mapped[int | None] = mapped_column(ForeignKey("coffees.id"), index=True)
    grinder_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"))
    machine_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"))
    recipe_id: Mapped[int | None] = mapped_column(ForeignKey("brew_recipes.id", ondelete="SET NULL"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    method: Mapped[str] = mapped_column(String(20), default="espresso")
    grind_setting: Mapped[str | None] = mapped_column(String(20))
    dose_g: Mapped[float] = mapped_column(Float)
    yield_g: Mapped[float] = mapped_column(Float)
    time_s: Mapped[float | None] = mapped_column(Float)
    temp_c: Mapped[float | None] = mapped_column(Float)
    pressure_bar: Mapped[float | None] = mapped_column(Float)
    preinfusion_s: Mapped[float | None] = mapped_column(Float)
    tds: Mapped[float | None] = mapped_column(Float)
    ratio: Mapped[float | None] = mapped_column(Float)
    ey_pct: Mapped[float | None] = mapped_column(Float)
    # Sensory scales: acidity/bitterness/body/sweetness/aroma 1..5, score 1..5
    acidity: Mapped[int | None]
    bitterness: Mapped[int | None]
    body: Mapped[int | None]
    sweetness: Mapped[int | None]
    aroma: Mapped[int | None]
    score: Mapped[int | None]
    # Optional cupping scores 0..10: {fragrance, flavor, aftertaste, acidity, body, balance, overall}
    cupping: Mapped[dict[str, float] | None] = mapped_column(JSON)
    # Flavor notes: keys of the flavor wheel (bloom_pro/services/flavor_wheel.json)
    flavor_notes: Mapped[list[str] | None] = mapped_column(JSON)
    channeling: Mapped[bool] = mapped_column(default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    suggestion: Mapped[str | None] = mapped_column(Text)
    is_dialed_in: Mapped[bool] = mapped_column(default=False)
    days_off_roast: Mapped[int | None]
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class BaristaJournal(IdMixin, Base):
    __tablename__ = "barista_journal"
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


DRINK_CATEGORIES = ("espresso", "con_leche", "frias", "filtrados", "sin_cafe", "otras")


class DrinkGuide(IdMixin, TimestampMixin, Base):
    """Step-by-step preparation guide for a drink, optionally linked to a product sold in the POS."""

    __tablename__ = "drink_guides"
    name: Mapped[str] = mapped_column(String(120))
    base_key: Mapped[str | None] = mapped_column(String(60))  # classic it was copied from
    category: Mapped[str] = mapped_column(String(20), default="otras")
    description: Mapped[str | None] = mapped_column(Text)
    cup: Mapped[str | None] = mapped_column(String(80))
    serving: Mapped[str | None] = mapped_column(String(80))
    difficulty: Mapped[int] = mapped_column(default=1)  # 1..3
    total_time_s: Mapped[int | None]
    # [{"kind": "equipo"|"ingrediente"|"preparación", "text": "...", "qty": "18 g"}]
    prerequisites: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    # [{"title": "...", "detail": "...", "duration_s": 30, "tip": "...", "icon": "extract"}]
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    # Bottom-to-top cup layers: [{"kind": "espresso", "ratio": 1}, {"kind": "milk", "ratio": 4}]
    layers: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    hot: Mapped[bool] = mapped_column(default=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), unique=True)
    active: Mapped[bool] = mapped_column(default=True)
    # Extras shown in the "Info" tab: ["tip", ...], [{"name": "...", "detail": "..."}], ["Molino", ...]
    tips: Mapped[list[str]] = mapped_column(JSON, default=list)
    variations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    equipment: Mapped[list[str]] = mapped_column(JSON, default=list)
    origin: Mapped[str | None] = mapped_column(String(80))
    caffeine: Mapped[str | None] = mapped_column(String(10))  # sin | bajo | medio | alto
    # Starred by the owner: shown in the "Destacadas" carousel next to the featured classics.
    featured: Mapped[bool] = mapped_column(default=False)


class DrinkGuideFavorite(IdMixin, Base):
    """A user's favorite guide: ``ref`` is ``classic:<key>`` or ``guide:<id>``."""

    __tablename__ = "drink_guide_favorites"
    __table_args__ = (UniqueConstraint("user_id", "ref"),)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    ref: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
