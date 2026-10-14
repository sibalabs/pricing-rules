import pytest

from pricing_rules.cli import main, parse_tiers


def test_tiers_parse():
    tiers = parse_tiers("30:0.10,60:0.2")
    assert [(t.min_idle_days, str(t.discount)) for t in tiers] == [(30, "0.10"), (60, "0.2")]


def test_cli_prints_a_table(tmp_path, capsys):
    f = tmp_path / "p.csv"
    f.write_text("sku,cost,price,stock,idle_days\nA,4.00,12.00,10,45\nB,4.00,12.00,0,45\n")
    assert main([str(f)]) == 0
    out = capsys.readouterr().out
    assert "A" in out and "discount" in out and "out of stock" in out


@pytest.mark.parametrize("content", ["sku,cost\nA,1\n", "sku,cost,price,stock,idle_days\nA,x,2,1,1\n"])
def test_cli_reports_bad_input_without_a_traceback(tmp_path, capsys, content):
    f = tmp_path / "bad.csv"
    f.write_text(content)
    assert main([str(f)]) == 2
    assert capsys.readouterr().err.startswith("error:")


def test_cli_reports_a_missing_file(capsys):
    assert main(["/nope.csv"]) == 2
