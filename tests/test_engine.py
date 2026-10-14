import random
from decimal import Decimal

import pytest

from pricing_rules import Action, Policy, Product, Tier, floor_price, money, suggest

D = Decimal
POLICY = Policy(min_margin=D("0.20"), tiers=(Tier(30, D("0.10")), Tier(60, D("0.20")), Tier(90, D("0.30"))))


def product(cost: str = "4.00", price: str = "12.00", stock: int = 10, idle: int = 45) -> Product:
    return Product("SKU", money(cost), money(price), stock, idle)


def test_floor_is_cost_divided_by_one_minus_margin():
    assert floor_price(product(cost="8.00"), POLICY) == D("10.00")


def test_recently_sold_stock_is_left_alone():
    s = suggest(product(idle=5), POLICY)
    assert s.action is Action.HOLD and s.new_price == s.current_price
    assert "below the first tier" in s.reason


def test_the_tier_matches_how_long_the_stock_has_been_idle():
    assert suggest(product(idle=30), POLICY).discount == D("0.1000")
    assert suggest(product(idle=75), POLICY).discount == D("0.2000")
    assert suggest(product(idle=500), POLICY).discount == D("0.3000")


def test_a_price_already_below_the_floor_is_held_never_raised():
    s = suggest(product(cost="8.20", price="10.00", idle=95), POLICY)  # floor is 10.25, above the price
    assert s.action is Action.HOLD and s.new_price == D("10.00") and "no room" in s.reason


def test_partial_room_is_used_up_to_the_floor_and_explained():
    s = suggest(product(cost="8.00", price="12.00", idle=95), POLICY)  # 30% would be 8.40, floor is 10.00
    assert s.new_price == D("10.00") and s.limited_by_floor
    assert "capped to 10.00" in s.reason and s.discount == D("0.1667")


def test_out_of_stock_is_never_discounted():
    assert suggest(product(stock=0, idle=200), POLICY).reason == "out of stock"


def test_max_discount_caps_the_tiers():
    policy = Policy(min_margin=D("0.10"), tiers=(Tier(10, D("0.40")),), max_discount=D("0.25"))
    assert suggest(product(cost="1.00", price="10.00", idle=20), policy).discount == D("0.2500")


def test_rounding_goes_up_so_the_floor_is_never_breached():
    # 3.33 / 0.8 = 4.1625, which must round UP to 4.17 (rounding down would breach the 20% floor)
    p = product(cost="3.33", price="4.30", idle=100)
    s = suggest(p, POLICY)
    assert s.new_price == D("4.17")
    assert (s.new_price - p.cost) / s.new_price >= D("0.20")


def test_float_input_does_not_create_artefacts():
    assert money(0.1) + money(0.2) == D("0.3")


@pytest.mark.parametrize(
    "kwargs",
    [{"cost": D(0)}, {"price": D(-1)}, {"stock": -1}, {"idle_days": -1}],
)
def test_bad_products_are_rejected(kwargs):
    base = {"sku": "X", "cost": D(1), "price": D(2), "stock": 1, "idle_days": 1}
    with pytest.raises(ValueError):
        Product(**{**base, **kwargs})


@pytest.mark.parametrize(
    "policy_args",
    [
        {"min_margin": D("1")},
        {"min_margin": D("-0.1")},
        {"max_discount": D("1")},
        {"tiers": ()},
        {"tiers": (Tier(60, D("0.2")), Tier(30, D("0.1")))},   # days must rise
        {"tiers": (Tier(30, D("0.3")), Tier(60, D("0.1")))},   # discounts must not fall
        {"tiers": (Tier(30, D("1.5")),)},
    ],
)
def test_bad_policies_are_rejected(policy_args):
    args = {"min_margin": D("0.2"), "tiers": (Tier(30, D("0.1")),), **policy_args}
    with pytest.raises(ValueError):
        Policy(**args)


def test_invariants_hold_across_thousands_of_random_products():
    """Whatever the inputs: never above the current price, never below the floor unless already below it."""
    rng = random.Random(7)
    for _ in range(5000):
        cost = money(round(rng.uniform(0.5, 200), 2))
        price = money(round(float(cost) * rng.uniform(0.8, 3.0), 2))
        margin = money(round(rng.uniform(0, 0.6), 2))
        policy = Policy(min_margin=margin, tiers=POLICY.tiers, max_discount=D("0.5"))
        p = Product("R", cost, price, rng.randint(0, 50), rng.randint(0, 200))
        s = suggest(p, policy)
        floor = floor_price(p, policy)
        assert s.new_price <= p.price
        assert s.action is Action.HOLD or s.new_price >= floor
        if s.action is Action.DISCOUNT:
            assert (s.new_price - p.cost) / s.new_price >= margin
