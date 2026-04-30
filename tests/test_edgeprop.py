from datetime import date
from pathlib import Path

from sg_condo_agent.fetchers.edgeprop import _load_cookie, parse_edgeprop_response


SAMPLE = [
    {
        "contract_date": 1776009600,  # Apr 12 2026 UTC
        "unit": "#14-38 ",
        "address": "89 HOUGANG AVENUE 2",
        "area_sqft": 1012,
        "bedrooms": 3,
        "transacted_price": 2080000,
        "type_of_sale": "Resale",
        "tenure": "99 yrs from 24/12/2018",
    },
    {
        "contract_date": 1576800000,  # Dec 20 2019 UTC
        "unit": "#14-38",
        "address": "89 HOUGANG AVENUE 2",
        "area_sqft": 1012,
        "bedrooms": 3,
        "transacted_price": 1500000,
        "type_of_sale": "New Sale",
        "tenure": "99 yrs from 24/12/2018",
    },
    {
        "contract_date": 1700000000,
        "unit": "#10-12",
        "address": "85 HOUGANG AVENUE 2",
        "area_sqft": 689,
        "bedrooms": 2,
        "transacted_price": 1200000,
        "type_of_sale": "Resale",
    },
]


def test_parse_extracts_unit_number():
    trades = parse_edgeprop_response(SAMPLE)
    assert all(t.unit_number for t in trades)
    assert trades[0].unit_number == "14-38"


def test_parse_extracts_block_from_address():
    trades = parse_edgeprop_response(SAMPLE)
    assert trades[0].block == "89"
    assert trades[2].block == "85"


def test_parse_uses_bedrooms_for_unit_type():
    trades = parse_edgeprop_response(SAMPLE)
    assert trades[0].unit_type == "3BR"
    assert trades[2].unit_type == "2BR"


def test_parse_converts_unix_timestamp_to_date():
    trades = parse_edgeprop_response(SAMPLE)
    assert trades[0].contract_date == date(2026, 4, 12)
    assert trades[1].contract_date == date(2019, 12, 20)


def test_parse_pair_key_groups_same_unit_across_floor_bands():
    trades = parse_edgeprop_response(SAMPLE)
    # Two trades of #14-38 should share pair_key.
    same_unit = [t for t in trades if t.unit_number == "14-38"]
    assert len(same_unit) == 2
    assert same_unit[0].pair_key == same_unit[1].pair_key


def test_load_cookie_returns_none_when_env_unset(monkeypatch):
    monkeypatch.delenv("EDGEPROP_COOKIE_FILE", raising=False)
    assert _load_cookie() is None


def test_load_cookie_returns_none_for_empty_file(monkeypatch, tmp_path: Path):
    f = tmp_path / "cookie.txt"
    f.write_text("")
    monkeypatch.setenv("EDGEPROP_COOKIE_FILE", str(f))
    assert _load_cookie() is None


def test_load_cookie_returns_text_when_file_populated(monkeypatch, tmp_path: Path):
    f = tmp_path / "cookie.txt"
    f.write_text("session=abc123\n")
    monkeypatch.setenv("EDGEPROP_COOKIE_FILE", str(f))
    assert _load_cookie() == "session=abc123"


def test_load_cookie_returns_none_when_path_missing(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("EDGEPROP_COOKIE_FILE", str(tmp_path / "does_not_exist"))
    assert _load_cookie() is None
