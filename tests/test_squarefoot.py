from datetime import date
from pathlib import Path
from sg_condo_agent.fetchers.squarefoot import parse_squarefoot_html

FIXTURE = Path(__file__).parent / "fixtures" / "squarefoot_florence.html"


def test_parse_returns_all_rows():
    trades = parse_squarefoot_html(FIXTURE.read_text())
    assert len(trades) == 3


def test_parse_extracts_block_and_floor():
    trades = parse_squarefoot_html(FIXTURE.read_text())
    t = next(t for t in trades if t.area_sqft == 689 and t.contract_date == date(2024, 6, 1))
    assert t.block == "80"
    assert t.floor_range == "06-10"


def test_parse_handles_price_and_area():
    trades = parse_squarefoot_html(FIXTURE.read_text())
    t = next(t for t in trades if t.contract_date == date(2019, 3, 1))
    assert t.price_sgd == 1_100_000
    assert t.area_sqft == 689
