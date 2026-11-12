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


class PublicFlavorNote(BaseModel):
    key: str
    label: str
    category: str  # top-level wheel category (color token suffix: `color`)
    color: str


class PublicCoffee(BaseModel):
    """Coffee in use shown to customers (Pro barista: "Café de hoy"), linked to the products that
    use it (recipe) and to the options of the "Tipo de café" modifier group."""

    id: int
    name: str
    role: str  # house | decaf | origin
    role_label: str
    roaster: str | None = None
    origin: str | None = None
    variety: str | None = None
    process: str | None = None
    altitude_m: int | None = None
    roast_point: str | None = None
    roast_label: str | None = None
    notes: list[PublicFlavorNote] = []
    profile: dict[str, int] | None = None  # body/aroma/sweetness/bitterness/acidity 1..5
    product_ids: list[int] = []
    modifier_ids: list[int] = []


class PublicWifi(BaseModel):
    """«WiFi» button (Pro): network, password and a QR (PNG data URL) to join it."""

    ssid: str
    password: str = ""
    qr: str | None = None


class PublicMenuOut(BaseModel):
    business_name: str
    show_prices: bool
    message: str
    categories: list[PublicCategory]
    tag_labels: dict[str, str] = {}
    combos: list[PublicCombo] = []  # active combos (Pro `promos`)
    coffees: list[PublicCoffee] = []  # coffees in use (Pro barista)
    wifi: PublicWifi | None = None  # «WiFi» button, when the café turned it on (Pro)
