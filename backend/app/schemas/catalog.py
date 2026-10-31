from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORM


# ---------- Product categories ----------
class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color: str = "amber"
    icon: str = "coffee"
    sort_order: int = 0
    active: bool = True


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    color: str | None = None
    icon: str | None = None
    sort_order: int | None = None
    active: bool | None = None


class CategoryOut(ORM):
    id: int
    name: str
    color: str
    icon: str
    sort_order: int
    active: bool
    product_count: int = 0


class CategoryRef(ORM):
    id: int
    name: str
    color: str
    icon: str


# ---------- Products ----------
class RecipeItemIn(BaseModel):
    stock_item_id: int
    qty: float = Field(gt=0)


class RecipeItemOut(BaseModel):
    id: int | None = None
    stock_item_id: int
    stock_item_name: str
    unit: str
    qty: float
    unit_cost_cents: float
    line_cost_cents: float


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category_id: int | None = None
    description: str | None = None
    price_cents: int = Field(ge=0)
    image_path: str | None = None
    color: str | None = None
    active: bool = True
    show_in_pos: bool = True
    stock_item_id: int | None = None
    sort_order: int = 0
    recipe_items: list[RecipeItemIn] = []
    modifier_group_ids: list[int] = []


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category_id: int | None = None
    description: str | None = None
    price_cents: int | None = Field(default=None, ge=0)
    image_path: str | None = None
    color: str | None = None
    active: bool | None = None
    show_in_pos: bool | None = None
    stock_item_id: int | None = None
    sort_order: int | None = None
    recipe_items: list[RecipeItemIn] | None = None
    modifier_group_ids: list[int] | None = None


class ProductOut(BaseModel):
    id: int
    name: str
    category_id: int | None
    category: CategoryRef | None
    description: str | None
    price_cents: int
    image_path: str | None
    color: str | None
    active: bool
    show_in_pos: bool
    stock_item_id: int | None
    stock_item_name: str | None = None
    sort_order: int
    cost_cents: int
    margin_pct: float | None
    recipe_items: list[RecipeItemOut]
    modifier_group_ids: list[int]
    updated_at: datetime | None = None


class BulkPriceIn(BaseModel):
    category_id: int | None = None
    percent: float = Field(gt=-90, lt=1000)
    round_to_cents: int = Field(default=0, ge=0)
    dry_run: bool = False


class BulkPriceRow(BaseModel):
    product_id: int
    name: str
    category_id: int | None
    old_cents: int
    new_cents: int


class BulkPriceOut(BaseModel):
    applied: bool
    count: int
    items: list[BulkPriceRow]


class PriceHistoryOut(BaseModel):
    id: int
    product_id: int
    old_cents: int
    new_cents: int
    change_pct: float | None
    user_id: int | None
    user_name: str | None
    ts: datetime


# ---------- Modifiers ----------
class ModifierRecipeItemIn(BaseModel):
    stock_item_id: int
    qty_delta: float


class ModifierRecipeItemOut(BaseModel):
    id: int
    stock_item_id: int
    stock_item_name: str
    unit: str
    qty_delta: float


class ModifierIn(BaseModel):
    id: int | None = None
    name: str = Field(min_length=1, max_length=80)
    price_delta_cents: int = 0
    sort_order: int = 0
    recipe_items: list[ModifierRecipeItemIn] = []


class ModifierOut(BaseModel):
    id: int
    name: str
    price_delta_cents: int
    sort_order: int
    recipe_items: list[ModifierRecipeItemOut]


class ModifierGroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    min_select: int = Field(default=0, ge=0)
    max_select: int = Field(default=1, ge=1)
    modifiers: list[ModifierIn] = []


class ModifierGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    min_select: int | None = Field(default=None, ge=0)
    max_select: int | None = Field(default=None, ge=1)
    modifiers: list[ModifierIn] | None = None


class ModifierGroupOut(BaseModel):
    id: int
    name: str
    min_select: int
    max_select: int
    modifiers: list[ModifierOut]
    product_ids: list[int]


# ---------- POS ----------
class PosModifier(BaseModel):
    id: int
    name: str
    price_delta_cents: int


class PosModifierGroup(BaseModel):
    id: int
    name: str
    min_select: int
    max_select: int
    modifiers: list[PosModifier]


class PosCategory(BaseModel):
    id: int
    name: str
    color: str
    icon: str


class PosProduct(BaseModel):
    id: int
    name: str
    price_cents: int
    category_id: int | None
    color: str | None
    image_path: str | None
    modifier_groups: list[PosModifierGroup]


class PosCatalogOut(BaseModel):
    categories: list[PosCategory]
    products: list[PosProduct]
