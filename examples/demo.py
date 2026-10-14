"""Run: python examples/demo.py"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))

from pricing_rules.cli import main  # noqa: E402

main([str(pathlib.Path(__file__).parent / "products.csv")])
