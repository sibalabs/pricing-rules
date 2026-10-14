<div align="center">

# pricing-rules

**Suggest discounts for slow-moving stock, and never go below your margin floor.**

[![tests](https://github.com/sibalabs/pricing-rules/actions/workflows/tests.yml/badge.svg)](https://github.com/sibalabs/pricing-rules/actions/workflows/tests.yml) ![python](https://img.shields.io/badge/python-3.10%2B-blue) ![deps](https://img.shields.io/badge/dependencies-0-brightgreen) ![license](https://img.shields.io/badge/license-MIT-lightgrey)

</div>

---

## The problem

Stock that sits unsold ties up cash, so discounting it makes sense. But a discount rule that doesn't know your costs will eventually sell something at a loss, and an AI agent that "optimises prices" can do it faster.

**pricing-rules keeps the decision small, explainable and safe.** Tiers decide *how much* to discount based on how long stock has sat. A margin floor decides *how far it's allowed to go*, and the floor always wins. Every suggestion comes with a plain-English reason, so a person can approve it in seconds.

```
 product (cost, price, stock, idle days) ──► tier discount ──► capped by max discount ──► capped by margin floor ──► suggestion + reason
```

## Quick start

```bash
pip install -e .
python examples/demo.py
```

```
SKU       ACTION          NOW      NEW    OFF  REASON
-----------------------------------------------------
MUG-01    hold          12.00    12.00     0%  idle 12 days, below the first tier (30 days)
MUG-02    discount      12.00    10.80    10%  idle 45 days, tier discount 10%
TEE-08    discount      19.00    13.30    30%  idle 120 days, tier discount 30%
CAP-03    discount      12.00    10.00    17%  idle 95 days, tier discount 30%, capped to 10.00 by the 20% margin floor
VASE-9    hold          10.00    10.00     0%  no room: price is already at or near the margin floor (10.25)
LAMP-2    hold          64.00    64.00     0%  out of stock
```

As a library:

```python
from decimal import Decimal
from pricing_rules import Policy, Product, Tier, money, suggest

policy = Policy(min_margin=Decimal("0.20"),
                tiers=(Tier(30, Decimal("0.10")), Tier(60, Decimal("0.20")), Tier(90, Decimal("0.30"))))

item = Product(sku="CAP-03", cost=money("8.00"), price=money("12.00"), stock=18, idle_days=95)
result = suggest(item, policy)

result.new_price   # Decimal('10.00')
result.reason      # 'idle 95 days, tier discount 30%, capped to 10.00 by the 20% margin floor'
```

From the command line, with your own CSV (`sku,cost,price,stock,idle_days`):

```bash
pricing-rules products.csv --min-margin 0.25 --tiers "30:0.10,60:0.20,90:0.30"
```

## The rules

| # | Rule | Why |
|---|---|---|
| 1 | **Floor price = cost ÷ (1 − min margin)**, rounded **up** to the cent | The one number nothing may go below |
| 2 | A discount never takes the price below the floor. If the tier asks for more, it's capped and the reason says so | Safety beats the tier table |
| 3 | A price already at or below the floor is **held**, never raised | The engine suggests discounts; it doesn't reprice upward |
| 4 | Out-of-stock products are never discounted | Nothing to clear |
| 5 | Idle days pick the tier: the highest tier reached applies | Deeper discounts for staler stock |
| 6 | `max_discount` caps every tier | A typo in a tier can't produce a 90% sale |
| 7 | All money is `Decimal`; rounding is always upward | No float artefacts, no rounding breaching the floor |
| 8 | Bad products and bad policies are rejected up front | Garbage in never reaches a price |

Margin means `(price − cost) / price`.

## Tested with more than examples

Besides the unit tests, one test throws **5,000 random products and policies** at the engine and asserts that, whatever the inputs, a suggestion never exceeds the current price and a discount never lands below the margin floor.

## Design decisions

- **Suggest, don't apply.** The output is a list of explained suggestions. Applying them is a separate step, ideally one a person approves (see [approval-gate](https://github.com/sibalabs/approval-gate)).
- **Rules, not a model.** A tier table is predictable, auditable and explainable to a shop owner. A model can *propose* inputs or tiers; it shouldn't be what guarantees the floor.
- **Reasons are part of the output.** "Capped to 10.00 by the 20% margin floor" is what lets a human trust it without re-deriving the maths.
- **Zero dependencies.** Standard library only.

## Limits (read these)

- It only discounts. It ignores demand, seasonality, competitor prices and shipping costs. Fold those into `cost` or add rules as needed.
- One cost per product. Landed cost, fees and VAT/sales tax are assumed to be included already.
- Tiers are on idle days only. Stock quantity or expiry dates would be natural extra rules.
- Prices are rounded up to the cent, so a suggestion can be a cent higher than the exact tier maths. That's deliberate.

## Project layout

```
src/pricing_rules/engine.py   Product, Policy, Tier, suggest() (~140 lines, the whole rule engine)
src/pricing_rules/cli.py      CSV in, table out
tests/                        26 tests, including the 5,000-case invariant check
examples/                     demo.py and an invented products.csv
```

## Development

```bash
pip install -e ".[dev]"
pytest && ruff check . && mypy
```

---

Built by [Siba Labs](https://www.upwork.com/). All example data is invented. MIT licensed.
