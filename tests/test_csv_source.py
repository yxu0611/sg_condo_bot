from datetime import date
from pathlib import Path

from sg_condo_agent.condos import get
from sg_condo_agent.fetchers.csv_source import load_csv

FIXTURE = Path(__file__).parent / "fixtures" / "sample_ura.csv"
FLORENCE = get("florence")


def test_load_csv_parses_all_rows():
    trades = load_csv(FIXTURE, FLORENCE)
    assert len(trades) == 5


def test_load_csv_parses_price_with_commas():
    trades = load_csv(FIXTURE, FLORENCE)
    assert trades[0].price_sgd == 1_100_000


def test_load_csv_parses_floor_range():
    trades = load_csv(FIXTURE, FLORENCE)
    assert trades[0].floor_range == "06-10"


def test_load_csv_parses_date_mon_yy():
    trades = load_csv(FIXTURE, FLORENCE)
    assert trades[0].contract_date == date(2019, 3, 1)


def test_load_csv_handles_decimal_sqft():
    trades = load_csv(FIXTURE, FLORENCE)
    assert trades[0].area_sqft == 689


def test_load_csv_filters_to_named_project():
    other = get("Some Other Project")
    assert load_csv(FIXTURE, other) == []
