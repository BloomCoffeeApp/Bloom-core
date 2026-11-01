from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text, UniqueConstraint, false, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin, utcnow


class ProductCategory(IdMixin, TimestampMixin, Base):
    __tablename__ = "product_categories"
    name: Mapped[str] = mapped_column(String(80))
    color: Mapped[str] = mapped_column(String(20), default="amber")
    icon: Mapped[str] = mapped_column(String(40), default="coffee")
    sort_order: Mapped[int] = mapped_column(default=0)
    active: Mapped[bool] = mapped_column(default=True)
    # Whether its products go to the order screen (bar/kitchen); e.g. bakery handed over at the counter: no.
    send_to_orders: Mapped[bool] = mapped_column(default=True, server_default=true())
    # Pro (`orders_pro`): station whose screen prepares this category (None = the first station).
    station_id: Mapped[int | None] = mapped_column(ForeignKey("order_stations.id", ondelete="SET NULL"))


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
    # Customer-facing extras (menu detail sheet). `description` is the short line shown on the card.
    long_description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str] | None] = mapped_column(JSON)  # codes from catalog.PRODUCT_TAGS
    featured: Mapped[bool] = mapped_column(default=False, server_default=false())
    # Target preparation time on the order screen (None = the channel's default).
    prep_minutes: Mapped[int | None]

    recipe_items: Mapped[list["RecipeItem"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    # Sizes this product is sold in (empty = single price/recipe, the classic behaviour).
    sizes: Mapped[list["ProductSize"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="ProductSize.id"
    )


class Size(IdMixin, TimestampMixin, Base):
    """Reusable size list defined by each business (\"Chico 8 oz\", \"Grande 16 oz\"…)."""

    __tablename__ = "sizes"
    name: Mapped[str] = mapped_column(String(60))
    short_label: Mapped[str] = mapped_column(String(12))
    volume_ml: Mapped[int | None]
    sort_order: Mapped[int] = mapped_column(default=0)
    active: Mapped[bool] = mapped_column(default=True)


class ProductSize(IdMixin, Base):
    """A size a product is sold in: own price, and its recipe = base recipe × recipe_scale with
    per-stock-item overrides (ProductSizeRecipeItem replaces the scaled qty; 0 = not used)."""

    __tablename__ = "product_sizes"
    __table_args__ = (UniqueConstraint("product_id", "size_id"),)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    size_id: Mapped[int] = mapped_column(ForeignKey("sizes.id"))
    price_cents: Mapped[int] = mapped_column(default=0)
    recipe_scale: Mapped[float] = mapped_column(Float, default=1.0)
    is_default: Mapped[bool] = mapped_column(default=False)
    product: Mapped[Product] = relationship(back_populates="sizes")
    size: Mapped[Size] = relationship(lazy="joined")
    recipe_items: Mapped[list["ProductSizeRecipeItem"]] = relationship(cascade="all, delete-orphan")


class ProductSizeRecipeItem(IdMixin, Base):
    __tablename__ = "product_size_recipe_items"
    product_size_id: Mapped[int] = mapped_column(ForeignKey("product_sizes.id", ondelete="CASCADE"), index=True)
    stock_item_id: Mapped[int] = mapped_column(ForeignKey("stock_items.id"))
    qty: Mapped[float] = mapped_column(Float)


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
    size_id: Mapped[int | None]  # set when the change was the price of one size (no FK: history outlives it)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
