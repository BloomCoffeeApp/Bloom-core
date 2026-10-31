from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin, utcnow


class ProductCategory(IdMixin, TimestampMixin, Base):
    __tablename__ = "product_categories"
    name: Mapped[str] = mapped_column(String(80))
    color: Mapped[str] = mapped_column(String(20), default="amber")
    icon: Mapped[str] = mapped_column(String(40), default="coffee")
    sort_order: Mapped[int] = mapped_column(default=0)
    active: Mapped[bool] = mapped_column(default=True)


class Product(IdMixin, TimestampMixin, Base):
    __tablename__ = "products"
    category_id: Mapped[int | None] = mapped_column(ForeignKey("product_categories.id"))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    price_cents: Mapped[int] = mapped_column(default=0)
    image_path: Mapped[str | None] = mapped_column(String(255))
    color: Mapped[str | None] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(default=True)
    show_in_pos: Mapped[bool] = mapped_column(default=True)
    # Products resold as-is (e.g. a bought croissant) point directly to one stock item.
    stock_item_id: Mapped[int | None] = mapped_column(ForeignKey("stock_items.id"))
    sort_order: Mapped[int] = mapped_column(default=0)

    recipe_items: Mapped[list["RecipeItem"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class ModifierGroup(IdMixin, TimestampMixin, Base):
    __tablename__ = "modifier_groups"
    name: Mapped[str] = mapped_column(String(80))
    min_select: Mapped[int] = mapped_column(default=0)
    max_select: Mapped[int] = mapped_column(default=1)
    modifiers: Mapped[list["Modifier"]] = relationship(
        back_populates="group", cascade="all, delete-orphan", order_by="Modifier.sort_order"
    )


class ProductModifierGroup(Base):
    __tablename__ = "product_modifier_groups"
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    group_id: Mapped[int] = mapped_column(
        ForeignKey("modifier_groups.id", ondelete="CASCADE"), primary_key=True
    )


class Modifier(IdMixin, Base):
    __tablename__ = "modifiers"
    group_id: Mapped[int] = mapped_column(ForeignKey("modifier_groups.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    price_delta_cents: Mapped[int] = mapped_column(default=0)
    sort_order: Mapped[int] = mapped_column(default=0)
    group: Mapped[ModifierGroup] = relationship(back_populates="modifiers")
    recipe_items: Mapped[list["ModifierRecipeItem"]] = relationship(cascade="all, delete-orphan")


class ModifierRecipeItem(IdMixin, Base):
    """Stock delta applied when the modifier is chosen (negative qty_delta = consumes less)."""

    __tablename__ = "modifier_recipe_items"
    modifier_id: Mapped[int] = mapped_column(ForeignKey("modifiers.id", ondelete="CASCADE"))
    stock_item_id: Mapped[int] = mapped_column(ForeignKey("stock_items.id"))
    qty_delta: Mapped[float] = mapped_column(Float)


class RecipeItem(IdMixin, Base):
    __tablename__ = "recipe_items"
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    stock_item_id: Mapped[int] = mapped_column(ForeignKey("stock_items.id"))
    qty: Mapped[float] = mapped_column(Float)
    product: Mapped[Product] = relationship(back_populates="recipe_items")


class PriceHistory(IdMixin, Base):
    __tablename__ = "price_history"
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    old_cents: Mapped[int]
    new_cents: Mapped[int]
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
