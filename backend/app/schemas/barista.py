from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORM

METHOD_PATTERN = r"^(espresso|v60|chemex|aeropress|french_press|cold_brew|moka)$"


# ---------- Coffees ----------
class CoffeeBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    roaster: str | None = None
    origin: str | None = None
    variety: str | None = None
    process: str | None = None
    altitude_m: int | None = Field(default=None, ge=0, le=6000)
    roast_level: str | None = None
    roast_date: date | None = None
    tasting_notes: str | None = None
    stock_item_id: int | None = None
    active: bool = True


class CoffeeCreate(CoffeeBase):
    pass


class CoffeeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    roaster: str | None = None
    origin: str | None = None
    variety: str | None = None
    process: str | None = None
    altitude_m: int | None = Field(default=None, ge=0, le=6000)
    roast_level: str | None = None
    roast_date: date | None = None
    tasting_notes: str | None = None
    stock_item_id: int | None = None
    active: bool | None = None


class CoffeeOut(CoffeeBase, ORM):
    id: int
    days_off_roast: int | None = None
    window: str | None = None  # reposando | optimo | pasado | None (sin fecha)
    roast_min_days: int | None = None
    roast_max_days: int | None = None


# ---------- Equipment & maintenance ----------
class EquipmentBase(BaseModel):
    kind: str = Field(pattern=r"^(machine|grinder|other)$")
    name: str = Field(min_length=1, max_length=120)
    brand: str | None = None
    model: str | None = None
    grind_scale: str | None = None
    notes: str | None = None
    active: bool = True


class EquipmentCreate(EquipmentBase):
    shot_counter: int = Field(default=0, ge=0)


class EquipmentUpdate(BaseModel):
    kind: str | None = Field(default=None, pattern=r"^(machine|grinder|other)$")
    name: str | None = Field(default=None, min_length=1, max_length=120)
    brand: str | None = None
    model: str | None = None
    grind_scale: str | None = None
    notes: str | None = None
    active: bool | None = None
    shot_counter: int | None = Field(default=None, ge=0)


class MaintenanceCreate(BaseModel):
    equipment_id: int
    name: str = Field(min_length=1, max_length=120)
    every_days: int | None = Field(default=None, ge=1)
    every_shots: int | None = Field(default=None, ge=1)


class MaintenanceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    every_days: int | None = Field(default=None, ge=1)
    every_shots: int | None = Field(default=None, ge=1)


class MaintenanceOut(BaseModel):
    id: int
    equipment_id: int
    equipment_name: str
    name: str
    every_days: int | None
    every_shots: int | None
    last_done_at: datetime | None
    last_done_shots: int
    days_since: int | None
    shots_since: int
    progress_pct: float  # 0..100+ (max between days and shots)
    status: str  # due | soon | ok
    due_reason: str | None = None


class EquipmentOut(EquipmentBase, ORM):
    id: int
    shot_counter: int
    maintenance: list[MaintenanceOut] = []


# ---------- Recipes ----------
class RecipeStep(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    start_s: int = Field(ge=0)
    end_s: int | None = Field(default=None, ge=0)
    target_g: float | None = Field(default=None, ge=0)
    note: str | None = None


class RecipeBase(BaseModel):
    coffee_id: int | None = None
    method: str = Field(default="espresso", pattern=METHOD_PATTERN)
    name: str = Field(min_length=1, max_length=120)
    dose_g: float = Field(gt=0, le=2000)
    yield_g: float = Field(gt=0, le=10000)
    time_min_s: int | None = Field(default=None, ge=0)
    time_max_s: int | None = Field(default=None, ge=0)
    temp_c: float | None = Field(default=None, ge=0, le=100)
    pressure_bar: float | None = Field(default=None, ge=0, le=20)
    preinfusion_s: int | None = Field(default=None, ge=0)
    grind_ref: str | None = None
    steps: list[RecipeStep] | None = None
    notes: str | None = None


class RecipeCreate(RecipeBase):
    is_current: bool = False


class RecipeUpdate(BaseModel):
    coffee_id: int | None = None
    method: str | None = Field(default=None, pattern=METHOD_PATTERN)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    dose_g: float | None = Field(default=None, gt=0, le=2000)
    yield_g: float | None = Field(default=None, gt=0, le=10000)
    time_min_s: int | None = Field(default=None, ge=0)
    time_max_s: int | None = Field(default=None, ge=0)
    temp_c: float | None = Field(default=None, ge=0, le=100)
    pressure_bar: float | None = Field(default=None, ge=0, le=20)
    preinfusion_s: int | None = Field(default=None, ge=0)
    grind_ref: str | None = None
    steps: list[RecipeStep] | None = None
    notes: str | None = None
    is_current: bool | None = None


class RecipeOut(ORM):
    id: int
    coffee_id: int | None
    coffee_name: str | None = None
    method: str
    name: str
    dose_g: float
    yield_g: float
    ratio: float | None = None
    time_min_s: int | None
    time_max_s: int | None
    temp_c: float | None
    pressure_bar: float | None
    preinfusion_s: int | None
    grind_ref: str | None
    steps: list[dict[str, Any]] | None
    notes: str | None
    is_current: bool
    updated_at: datetime | None = None


# ---------- Dial-in ----------
class SuggestionAction(BaseModel):
    param: str
    direction: str
    amount: str | float | None = None


class Suggestion(BaseModel):
    id: str | None = None
    level: str  # ok | info | adjust | warning
    title: str
    detail: str
    action: SuggestionAction | None = None


class DialinIn(BaseModel):
    coffee_id: int | None = None
    recipe_id: int | None = None
    method: str = Field(default="espresso", pattern=METHOD_PATTERN)
    dose_g: float = Field(gt=0, le=2000)
    yield_g: float = Field(ge=0, le=10000)
    time_s: float | None = Field(default=None, ge=0)
    temp_c: float | None = Field(default=None, ge=0, le=100)
    tds: float | None = Field(default=None, ge=0, le=30)
    acidity: int | None = Field(default=None, ge=1, le=5)
    bitterness: int | None = Field(default=None, ge=1, le=5)
    sweetness: int | None = Field(default=None, ge=1, le=5)
    body: int | None = Field(default=None, ge=1, le=5)
    score: int | None = Field(default=None, ge=1, le=5)
    channeling: bool = False


class TargetOut(BaseModel):
    source: str  # recipe | default
    recipe_id: int | None = None
    recipe_name: str | None = None
    time_min_s: float | None = None
    time_max_s: float | None = None
    ratio: float | None = None
    ratio_min: float | None = None
    ratio_max: float | None = None
    dose_g: float | None = None
    yield_g: float | None = None
    temp_c: float | None = None
    grind_ref: str | None = None


class DialinOut(BaseModel):
    ratio: float | None
    ey_pct: float | None
    target: TargetOut
    flags: list[str]
    suggestions: list[Suggestion]


# ---------- Shots ----------
class ShotCreate(DialinIn):
    grinder_id: int | None = None
    machine_id: int | None = None
    grind_setting: str | None = Field(default=None, max_length=20)
    pressure_bar: float | None = Field(default=None, ge=0, le=20)
    preinfusion_s: float | None = Field(default=None, ge=0)
    notes: str | None = None
    is_dialed_in: bool = False


class ShotOut(ORM):
    id: int
    coffee_id: int | None
    coffee_name: str | None = None
    grinder_id: int | None
    grinder_name: str | None = None
    machine_id: int | None
    recipe_id: int | None
    user_id: int | None
    user_name: str | None = None
    method: str
    grind_setting: str | None
    dose_g: float
    yield_g: float
    time_s: float | None
    temp_c: float | None
    pressure_bar: float | None
    preinfusion_s: float | None
    tds: float | None
    ratio: float | None
    ey_pct: float | None
    acidity: int | None
    bitterness: int | None
    body: int | None
    sweetness: int | None
    score: int | None
    channeling: bool
    notes: str | None
    suggestions: list[Suggestion] = []
    is_dialed_in: bool
    days_off_roast: int | None
    ts: datetime


class ShotPage(BaseModel):
    items: list[ShotOut]
    total: int
    page: int
    page_size: int


class DialedInResult(BaseModel):
    shot: ShotOut
    recipe: RecipeOut | None


# ---------- Today / stats ----------
class CurrentEspresso(BaseModel):
    recipe: RecipeOut
    coffee: CoffeeOut | None
    last_dialed_shot: ShotOut | None


class TodayOut(BaseModel):
    current_espresso: CurrentEspresso | None
    shots_today: int
    avg_time_today: float | None
    maintenance_due: list[MaintenanceOut]


class StatPoint(BaseModel):
    id: int
    grind_setting: str | None
    grind_value: float | None
    time_s: float | None
    score: int | None
    ratio: float | None
    days_off_roast: int | None
    is_dialed_in: bool
    ts: datetime


class StatDay(BaseModel):
    date: date
    shots: int
    avg_time: float | None
    avg_score: float | None
    dialed_grind: str | None


class StatCalibration(BaseModel):
    id: int
    ts: datetime
    coffee_name: str | None
    grind_setting: str | None
    dose_g: float
    yield_g: float
    time_s: float | None
    ratio: float | None
    score: int | None
    days_off_roast: int | None


class StatsOut(BaseModel):
    coffee_id: int | None
    days: int
    points: list[StatPoint]
    daily: list[StatDay]
    calibrations: list[StatCalibration]


# ---------- Journal ----------
class JournalCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class JournalOut(ORM):
    id: int
    user_id: int | None
    user_name: str | None = None
    body: str
    ts: datetime


# ---------- Drink guides ----------
DRINK_CATEGORY_PATTERN = r"^(espresso|con_leche|frias|filtrados|sin_cafe|otras)$"
PREREQ_KIND_PATTERN = r"^(equipo|ingrediente|preparación)$"
STEP_ICON_PATTERN = r"^(grind|tamp|extract|steam|pour|stir|ice|bloom|wait|serve|heat|measure|press)$"
LAYER_KIND_PATTERN = r"^(espresso|crema|milk|foam|water|chocolate|ice|cream|syrup|tea|coffee)$"


class GuidePrerequisite(BaseModel):
    kind: str = Field(pattern=PREREQ_KIND_PATTERN)
    text: str = Field(min_length=1, max_length=200)
    qty: str | None = Field(default=None, max_length=60)


class GuideStep(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    detail: str = Field(default="", max_length=1000)
    duration_s: int | None = Field(default=None, ge=1, le=86400)
    tip: str | None = Field(default=None, max_length=500)
    icon: str | None = Field(default=None, pattern=STEP_ICON_PATTERN)


class GuideLayer(BaseModel):
    kind: str = Field(pattern=LAYER_KIND_PATTERN)
    ratio: float = Field(gt=0, le=100)


class DrinkGuideFields(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(default="otras", pattern=DRINK_CATEGORY_PATTERN)
    description: str | None = Field(default=None, max_length=2000)
    cup: str | None = Field(default=None, max_length=80)
    serving: str | None = Field(default=None, max_length=80)
    difficulty: int = Field(default=1, ge=1, le=3)
    total_time_s: int | None = Field(default=None, ge=0, le=7 * 86400)
    hot: bool = True
    prerequisites: list[GuidePrerequisite] = Field(default_factory=list, max_length=40)
    steps: list[GuideStep] = Field(default_factory=list, max_length=30)
    layers: list[GuideLayer] = Field(default_factory=list, max_length=12)


class ClassicDrink(DrinkGuideFields):
    key: str


class DrinkGuideCreate(BaseModel):
    """Either a full guide, or ``from_classic`` (copies that classic; given fields override it)."""

    from_classic: str | None = None
    product_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: str | None = Field(default=None, pattern=DRINK_CATEGORY_PATTERN)
    description: str | None = Field(default=None, max_length=2000)
    cup: str | None = Field(default=None, max_length=80)
    serving: str | None = Field(default=None, max_length=80)
    difficulty: int | None = Field(default=None, ge=1, le=3)
    total_time_s: int | None = Field(default=None, ge=0, le=7 * 86400)
    hot: bool | None = None
    prerequisites: list[GuidePrerequisite] | None = Field(default=None, max_length=40)
    steps: list[GuideStep] | None = Field(default=None, max_length=30)
    layers: list[GuideLayer] | None = Field(default=None, max_length=12)


class DrinkGuideUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: str | None = Field(default=None, pattern=DRINK_CATEGORY_PATTERN)
    description: str | None = Field(default=None, max_length=2000)
    cup: str | None = Field(default=None, max_length=80)
    serving: str | None = Field(default=None, max_length=80)
    difficulty: int | None = Field(default=None, ge=1, le=3)
    total_time_s: int | None = Field(default=None, ge=0, le=7 * 86400)
    hot: bool | None = None
    prerequisites: list[GuidePrerequisite] | None = Field(default=None, max_length=40)
    steps: list[GuideStep] | None = Field(default=None, max_length=30)
    layers: list[GuideLayer] | None = Field(default=None, max_length=12)
    product_id: int | None = None
    active: bool | None = None


class DrinkGuideOut(DrinkGuideFields, ORM):
    id: int
    base_key: str | None
    product_id: int | None
    product_name: str | None = None
    active: bool
    created_at: datetime
    updated_at: datetime


class GuideableProduct(BaseModel):
    id: int
    name: str
    category_name: str | None
    suggested_classic: str | None = None
