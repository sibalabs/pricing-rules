"""Command line: read a CSV of products, print suggestions.

    pricing-rules examples/products.csv --min-margin 0.20
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections.abc import Sequence
from decimal import InvalidOperation
from pathlib import Path

from .engine import Policy, Product, Suggestion, Tier, money, suggest_all

DEFAULT_TIERS = "30:0.10,60:0.20,90:0.30"


def parse_tiers(text: str) -> tuple[Tier, ...]:
    """'30:0.10,60:0.20' -> idle 30+ days gets 10%, idle 60+ days gets 20%."""
    tiers = []
    for part in text.split(","):
        days, _, rate = part.partition(":")
        tiers.append(Tier(int(days), money(rate)))
    return tuple(tiers)


def load_products(path: Path) -> list[Product]:
    with path.open(newline="") as handle:
        return [
            Product(
                sku=row["sku"],
                cost=money(row["cost"]),
                price=money(row["price"]),
                stock=int(row["stock"]),
                idle_days=int(row["idle_days"]),
            )
            for row in csv.DictReader(handle)
        ]


def format_table(suggestions: Sequence[Suggestion]) -> str:
    header = f"{'SKU':<10}{'ACTION':<10}{'NOW':>9}{'NEW':>9}{'OFF':>7}  REASON"
    lines = [header, "-" * len(header)]
    for s in suggestions:
        row = f"{s.sku:<10}{s.action.value:<10}{s.current_price:>9}{s.new_price:>9}{s.discount:>7.0%}"
        lines.append(f"{row}  {s.reason}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pricing-rules", description=__doc__)
    parser.add_argument("csv", type=Path, help="columns: sku,cost,price,stock,idle_days")
    parser.add_argument("--min-margin", default="0.20", help="margin floor, e.g. 0.20 (default)")
    parser.add_argument(
        "--tiers", default=DEFAULT_TIERS, help=f"idle_days:discount pairs (default {DEFAULT_TIERS})"
    )
    args = parser.parse_args(argv)

    try:
        policy = Policy(min_margin=money(args.min_margin), tiers=parse_tiers(args.tiers))
        products = load_products(args.csv)
    except (ValueError, KeyError, InvalidOperation, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print(format_table(suggest_all(products, policy)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
