import pytest

from services import energy_calculator as ec


def test_daily_kwh_formula():
    assert ec.daily_kwh(100, 2, 5) == pytest.approx(1.0)          # 100 W x 2 x 5 h / 1000
    assert ec.daily_kwh(9, 6, 5) == pytest.approx(0.27)


def test_monthly_kwh_formula():
    assert ec.monthly_kwh(1.0, 30) == pytest.approx(30.0)


def test_cost_formula():
    assert ec.energy_cost(30.0, 8.0) == pytest.approx(240.0)


def test_zero_boundaries():
    assert ec.daily_kwh(0, 1, 5) == 0
    assert ec.daily_kwh(100, 1, 0) == 0
    assert ec.energy_cost(0, 8) == 0


def test_standby_uses_idle_hours_only():
    # 5 W x 1 x (24-4) h / 1000 = 0.1 kWh
    assert ec.standby_daily_kwh(5, 1, 4) == pytest.approx(0.1)
    assert ec.standby_daily_kwh(5, 1, 24) == 0.0


def test_bill_estimate_adds_fixed_and_tax():
    b = ec.estimate_bill(100.0, fixed_charge=50.0, tax_percent=10.0)
    assert b["tax"] == pytest.approx(15.0)
    assert b["estimated_bill"] == pytest.approx(165.0)


def test_summary_totals_match_rows(appliances, tariff):
    s = ec.summarize(appliances, tariff)
    assert s["totals"]["monthly_kwh"] == pytest.approx(sum(r["monthly_kwh"] for r in s["rows"]))
    assert s["totals"]["energy_charge"] == pytest.approx(s["totals"]["monthly_kwh"] * tariff["base_rate"])
    assert sum(r["share_percent"] for r in s["rows"]) == pytest.approx(100.0, abs=0.01)
