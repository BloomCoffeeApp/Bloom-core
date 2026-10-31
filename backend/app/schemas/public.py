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


class PublicProduct(BaseModel):
    id: int
    name: str
    description: str | None = None
    price_cents: int | None = None
    color: str | None = None
    modifier_groups: list[PublicModifierGroup] = []


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
