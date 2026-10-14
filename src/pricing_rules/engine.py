"""Discount suggestions for slow-moving stock, with a margin floor that cannot be broken.

The rule that matters most: no suggestion ever prices a product below
`cost / (1 - min_margin)`. Everything else (tiers, caps, rounding) is built around that guarantee.

Money is `Decimal` throughout. Floats are never used for prices, so there are no 0.1 + 0.2 surprises.
Margin means (price - cost) / price.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from enum import Enum

CENT = Decimal("0.01")
RATE_PLACES = Decimal("0.0001")


def money(value: Decimal | int | float | str) -> Decimal:
    """Convert to Decimal without float artefacts (0.1 stays 0.1)."""
    return Decimal(str(value))


class Action(str, Enum):
    DISCOUNT = "discount"
    HOLD = "hold"


@dataclass(frozen=True)
class Product:
    sku: str
    cost: Decimal
    price: Decimal
    stock: int
    idle_days: int  # days since the last sale

    def __post_init__(self) -> None:
        if self.cost <= 0 or self.price <= 0:
            raise ValueError(f"{self.sku}: cost and price must be positive")
        if self.stock < 0 or self.idle_days < 0:
            raise ValueError(f"{self.sku}: stock and idle_days cannot be negative")


@dataclass(frozen=True)
class Tier:
    """Once a product has been idle for `min_idle_days`, discount it by `discount` (0.10 = 10%)."""

    min_idle_days: int
    discount: Decimal


@dataclass(frozen=True)
class Policy:
    min_margin: Decimal  # the floor, e.g. 0.20 means never sell below a 20% margin
    tiers: tuple[Tier, ...]
    max_discount: Decimal = Decimal("0.50")  # hard cap, whatever the tiers say

    def __post_init__(self) -> None:
        if not Decimal(0) <= self.min_margin < Decimal(1):
            raise ValueError("min_margin must be at least 0 and below 1")
        if not Decimal(0) < self.max_discount < Decimal(1):
            raise ValueError("max_discount must be above 0 and below 1")
        if not self.tiers:
            raise ValueError("at least one tier is required")
        for tier in self.tiers:
            if not Decimal(0) < tier.discount < Decimal(1) or tier.min_idle_days < 0:
                raise ValueError(f"invalid tier: {tier}")
        for earlier, later in zip(self.tiers, self.tiers[1:], strict=False):
            if later.min_idle_days <= earlier.min_idle_days or later.discount < earlier.discount:
                raise ValueError("tiers must have rising idle days and non-decreasing discounts")


@dataclass(frozen=True)
class Suggestion:
    sku: str
    action: Action
    current_price: Decimal
    new_price: Decimal
    discount: Decimal  # effective discount actually applied, 0 when holding
    floor_price: Decimal
    limited_by_floor: bool
    reason: str


def floor_price(product: Product, policy: Policy) -> Decimal:
    """Lowest allowed price. Rounded UP to the cent so rounding can never breach the margin."""
    return (product.cost / (1 - policy.min_margin)).quantize(CENT, rounding=ROUND_CEILING)


def _tier_for(idle_days: int, policy: Policy) -> Tier | None:
    reached = [t for t in policy.tiers if idle_days >= t.min_idle_days]
    return reached[-1] if reached else None


def _hold(product: Product, floor: Decimal, reason: str) -> Suggestion:
    price = product.price
    return Suggestion(product.sku, Action.HOLD, price, price, Decimal(0), floor, False, reason)


def suggest(product: Product, policy: Policy) -> Suggestion:
    """One product in, one explained suggestion out. Never raises the price, never breaks the floor."""
    floor = floor_price(product, policy)

    if product.stock == 0:
        return _hold(product, floor, "out of stock")

    tier = _tier_for(product.idle_days, policy)
    if tier is None:
        first = policy.tiers[0].min_idle_days
        return _hold(product, floor, f"idle {product.idle_days} days, below the first tier ({first} days)")

    rate = min(tier.discount, policy.max_discount)
    target = (product.price * (1 - rate)).quantize(CENT, rounding=ROUND_CEILING)
    limited = target < floor
    new_price = max(target, floor)

    if new_price >= product.price:
        return _hold(product, floor, f"no room: price is already at or near the margin floor ({floor})")

    applied = ((product.price - new_price) / product.price).quantize(RATE_PLACES)
    reason = f"idle {product.idle_days} days, tier discount {rate:.0%}"
    if limited:
        reason += f", capped to {new_price} by the {policy.min_margin:.0%} margin floor"
    return Suggestion(
        product.sku, Action.DISCOUNT, product.price, new_price, applied, floor, limited, reason
    )


def suggest_all(products: Iterable[Product], policy: Policy) -> list[Suggestion]:
    return [suggest(p, policy) for p in products]
