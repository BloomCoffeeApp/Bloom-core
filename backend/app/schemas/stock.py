from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORM

UNIT_PATTERN = r"^(g|ml|u)$"


class StockCategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class StockCategoryOut(ORM):
    id: int
    name: str
    item_count: int = 0


class StockItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category_id: int | None = None
    unit: str = Field(default="u", pattern=UNIT_PATTERN)
    min_qty: float = Field(default=0, ge=0)
    avg_cost_cents: float = Field(default=0, ge=0)
    default_supplier_id: int | None = None
    track_expiry: bool = False
    active: bool = True
    initial_qty: float = Field(default=0, ge=0)


class StockItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category_id: int | None = None
    unit: str | None = Field(default=None, pattern=UNIT_PATTERN)
    min_qty: float | None = Field(default=None, ge=0)
    avg_cost_cents: float | None = Field(default=None, ge=0)
    default_supplier_id: int | None = None
    track_expiry: bool | None = None
    active: bool | None = None


class PackageIn(BaseModel):
    id: int | None = None  # existing package (kept), or None = new
    name: str = Field(min_length=1, max_length=60)
    content_qty: float = Field(gt=0, le=1_000_000)  # base units (g/ml/u) per package
    barcode: str | None = Field(default=None, max_length=40)
    cost_cents: int | None = Field(default=None, ge=0)
    is_default: bool = False


class PackageOut(ORM):
    id: int
    name: str
    content_qty: float
    barcode: str | None
    cost_cents: int | None
    is_default: bool


class PackagesIn(BaseModel):
    packages: list[PackageIn] = Field(max_length=20)


class StockItemOut(BaseModel):
    id: int
    name: str
    category_id: int | None
    category_name: str | None
    unit: str
    current_qty: float
    min_qty: float
    avg_cost_cents: float
    default_supplier_id: int | None
    supplier_name: str | None
    track_expiry: bool
    active: bool
    status: str  # ok|low|out
    value_cents: int
    next_expiry: str | None = None
    # Free plan: visible but not usable in recipes or stock movements (services/free_plan.py).
    locked: bool = False
    # Package types (stock stays in the base unit); the default one drives "4 envases + 730 ml".
    packages: list[PackageOut] = []


class MovementOut(BaseModel):
    id: int
    stock_item_id: int
    type: str
    qty: float
    unit_cost_cents: float
    balance_after: float
    ref_type: str | None
    ref_id: int | None
    reason: str | None
    user_id: int | None
    user_name: str | None
    ts: datetime


class AdjustIn(BaseModel):
    stock_item_id: int
    new_qty: float | None = None
    delta: float | None = None
    reason: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def _one_of(self) -> "AdjustIn":
        if (self.new_qty is None) == (self.delta is None):
            raise ValueError("Indicá la cantidad nueva o la diferencia (una sola)")
        return self


DISCARD_REASONS: dict[str, str] = {
    "expired": "Vencido",
    "spill": "Derrame / se cayó",
    "breakage": "Rotura",
    "leftover": "Sobrante de preparación",
    "other": "Otro",
}


class WasteIn(BaseModel):
    """Discard (merma). The amount is ONE of: `qty` (base units), `packages` of `package_id`, `all`
    (everything left, or everything left in `lot_id`)."""

    stock_item_id: int
    qty: float | None = Field(default=None, gt=0)
    package_id: int | None = None
    packages: float | None = Field(default=None, gt=0)
    all: bool = False
    lot_id: int | None = None
    reason_code: str | None = Field(default=None, pattern=r"^(expired|spill|breakage|leftover|other)$")
    note: str | None = Field(default=None, max_length=300)
    reason: str | None = Field(default=None, max_length=300)  # free text (older clients)

    @model_validator(mode="after")
    def _amount(self) -> "WasteIn":
        given = sum([self.qty is not None, self.packages is not None, self.all])
        if given != 1:
            raise ValueError("Indicá cuánto descartar: una cantidad, envases o todo")
        if self.packages is not None and self.package_id is None:
            raise ValueError("Elegí el envase")
        if not (self.reason_code or (self.reason or "").strip()):
            raise ValueError("Elegí un motivo")
        if self.reason_code == "other" and not (self.note or "").strip():
            raise ValueError("Contá brevemente qué pasó")
        return self


class QuickDiscardIn(BaseModel):
    """Small spills from the POS/barista ("se cayeron 10 ml de leche")."""

    stock_item_id: int
    qty: float = Field(gt=0)
    reason_code: str = Field(default="spill", pattern=r"^(expired|spill|breakage|leftover|other)$")
    note: str | None = Field(default=None, max_length=300)


class QuickItemOut(BaseModel):
    id: int
    name: str
    unit: str
    current_qty: float
    packages: list[PackageOut] = []


class LotOut(ORM):
    id: int
    qty_remaining: float
    expiry_date: date | None
    created_at: datetime


class CountCreate(BaseModel):
    category_id: int | None = None
    notes: str | None = None


class CountItemPatch(BaseModel):
    counted_qty: float | None = Field(default=None, ge=0)


class CountItemRow(BaseModel):
    id: int
    counted_qty: float | None = Field(default=None, ge=0)


class CountItemsPatch(BaseModel):
    items: list[CountItemRow]


class CountItemOut(BaseModel):
    id: int
    stock_item_id: int
    name: str
    unit: str
    category_id: int | None
    category_name: str | None
    expected_qty: float
    counted_qty: float | None
    diff_qty: float | None
    diff_value_cents: int | None
    avg_cost_cents: float


class CountOut(BaseModel):
    id: int
    status: str
    notes: str | None
    user_id: int | None
    user_name: str | None
    created_at: datetime
    updated_at: datetime | None
    total_items: int
    counted_items: int
    diff_value_cents: int
    items: list[CountItemOut] = []


class StockSummary(BaseModel):
    total_value_cents: int
    low_count: int
    out_count: int
    item_count: int


class SuggestionItem(BaseModel):
    stock_item_id: int
    name: str
    unit: str
    current_qty: float
    min_qty: float
    status: str
    daily_consumption: float
    suggested_qty: float
    avg_cost_cents: float
    est_cost_cents: int


class SuggestionGroup(BaseModel):
    supplier_id: int | None
    supplier_name: str
    items: list[SuggestionItem]
    total_est_cents: int
