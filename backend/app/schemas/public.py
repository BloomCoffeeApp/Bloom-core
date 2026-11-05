"""Schemas for the public (no-login) customer menu. Only customer-safe fields."""

from pydantic import BaseModel


class PublicModifier(BaseModel):
    id: int
    name: str
    price_delta_cents: int | None = None


class PublicModifierGroup(BaseModel):
    id: int
    name: str
    min_select: int
    max_select: int
    modifiers: list[PublicModifier]


class PublicSize(BaseModel):
    id: int  # size id
    name: str
    short_label: str
    volume_ml: int | None = None
    price_cents: int | None = None
    is_default: bool = False


class PublicPromo(BaseModel):
    """Active promotion of a product (Pro `promos`): badge + promo price of the shown size."""

    name: str
    label: str
    price_cents: int | None = None


class PublicCombo(BaseModel):
    name: str
    price_cents: int | None = None
    items: list[str] = []


class PublicProduct(BaseModel):
    id: int
    name: str
    description: str | None = None
    price_cents: int | None = None  # sized products: the default size's price
    color: str | None = None
    modifier_groups: list[PublicModifierGroup] = []
    long_description: str | None = None
    tags: list[str] = []  # codes; labels in `PublicMenuOut.tag_labels`
    featured: bool = False
    photo_url: str | None = None  # local menu only (/uploads/...)
    sizes: list[PublicSize] = []
    promo: PublicPromo | None = None


class PublicCategory(BaseModel):
    id: int | None
    name: str
    color: str | None = None
    icon: str | None = None
    products: list[PublicProduct]


class PublicMenuOut(BaseModel):
    business_name: str
    show_prices: bool
    message: str
    categories: list[PublicCategory]
    tag_labels: dict[str, str] = {}
    combos: list[PublicCombo] = []  # active combos (Pro `promos`)
