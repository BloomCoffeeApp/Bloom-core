"""Supplies consumed by channel ("Insumos según el canal"): any stock item a sold unit uses depending on
how it's served (salón: servilleta + sobre de azúcar; para llevar: vaso + tapa; delivery: vaso + tapa +
bolsa…). Configured by the café per category (default) and per product/size; empty by default.
See services/channel_supplies.py for the rules."""

from sqlalchemy import Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin

SUPPLY_CHANNELS = ("salon", "llevar", "delivery")


class ChannelSupply(IdMixin, Base):
    __tablename__ = "channel_supplies"
    __table_args__ = (
        Index("ix_channel_supplies_product", "product_id", "channel"),
        Index("ix_channel_supplies_category", "category_id", "channel"),
    )
    # Exactly one owner: a product, or a category (default for its products without their own list).
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("product_categories.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(10))  # salon | llevar | delivery (each its own full list)
    # NULL = every size; a size id = override for that size (its qty REPLACES the base one; 0 = not used).
    size_id: Mapped[int | None] = mapped_column(ForeignKey("sizes.id", ondelete="CASCADE"))
    stock_item_id: Mapped[int] = mapped_column(ForeignKey("stock_items.id", ondelete="CASCADE"))
    qty: Mapped[float] = mapped_column(Float, default=1)  # per unit sold
