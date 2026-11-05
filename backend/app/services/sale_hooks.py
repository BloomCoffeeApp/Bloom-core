"""Extension points of the checkout that Pro modules plug into (the free edition registers none).

- Pricing (`promos`): given the priced lines of a cart, return the best promotion per line.
- Rewards (`loyalty_pro`): validate stamp-card rewards redeemed in a sale and price a discount reward.
- After a sale / after a void: e.g. add or remove stamps, in the SAME transaction as the sale.

Hooks never commit; the caller (services/sales.py) owns the transaction.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import APP_DISPLAY_NAME


@dataclass
class QuoteLine:
    """A cart line as priced by the catalog (cents)."""

    index: int
    product_id: int
    category_id: int | None
    size_id: int | None
    qty: float
    base_price_cents: int  # size (or product) price, without modifiers
    unit_price_cents: int  # with modifiers
    gross_cents: int  # unit × qty


@dataclass
class LinePromo:
    promo_id: int | None
    name: str
    discount_cents: int


@dataclass
class RewardLine:
    """A $0 line redeemed from a stamp card."""

    index: int
    program_id: int
    product_id: int
    size_id: int | None
    qty: float


@dataclass
class RewardRequest:
    customer: Any  # app.models.Customer
    lines: list[RewardLine] = field(default_factory=list)
    sale_program_id: int | None = None  # discount reward on the whole sale
    amount_cents: int = 0  # what the discount reward applies to


PricingHook = Callable[[Session, list[QuoteLine]], dict[int, LinePromo]]
RewardHook = Callable[[Session, RewardRequest], tuple[int, str | None]]  # (discount_cents, label)
SaleHook = Callable[[Session, Any, Any], None]  # (db, sale, user)

_pricing: list[PricingHook] = []
_reward: list[RewardHook] = []
_after_sale: list[SaleHook] = []
_after_void: list[SaleHook] = []


def register(*, pricing: PricingHook | None = None, reward: RewardHook | None = None,
             after_sale: SaleHook | None = None, after_void: SaleHook | None = None) -> None:
    for hook, bucket in ((pricing, _pricing), (reward, _reward), (after_sale, _after_sale), (after_void, _after_void)):
        if hook is not None and hook not in bucket:
            bucket.append(hook)


def price_lines(db: Session, lines: list[QuoteLine]) -> dict[int, LinePromo]:
    """Best promotion per line index (first pricing hook that answers wins)."""
    out: dict[int, LinePromo] = {}
    for hook in _pricing:
        for idx, promo in (hook(db, lines) or {}).items():
            if idx not in out and promo.discount_cents > 0:
                out[idx] = promo
    return out


def rewards(db: Session, req: RewardRequest) -> tuple[int, str | None]:
    if not req.lines and req.sale_program_id is None:
        return 0, None
    if not _reward:
        raise HTTPException(402, f"Los premios de la tarjeta de sellos son parte de {APP_DISPLAY_NAME} Pro.")
    return _reward[0](db, req)


def after_sale(db: Session, sale: Any, user: Any) -> None:
    for hook in _after_sale:
        hook(db, sale, user)


def after_void(db: Session, sale: Any, user: Any) -> None:
    for hook in _after_void:
        hook(db, sale, user)
