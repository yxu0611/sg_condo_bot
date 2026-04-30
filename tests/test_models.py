from datetime import date
from florence_agent.models import Trade


def test_trade_psf_computed():
    t = Trade(
        contract_date=date(2024, 6, 1),
        block="80",
        floor_range="06-10",
        area_sqft=689,
        unit_type="2BR",
        price_sgd=1_350_000,
        tenure="99 yrs",
        sale_type="Resale",
    )
    assert round(t.psf) == 1959


def test_trade_pair_key_groups_same_unit():
    a = Trade(date(2020, 1, 1), "80", "06-10", 689, "2BR", 1_100_000, "99 yrs", "New Sale")
    b = Trade(date(2024, 6, 1), "80", "06-10", 689, "2BR", 1_350_000, "99 yrs", "Resale")
    assert a.pair_key == b.pair_key


def test_pair_key_prefers_unit_number_when_available():
    # Same block + same unit number → same pair_key, regardless of floor band.
    a = Trade(date(2020, 1, 1), "89", "06-10", 689, "2BR", 1_100_000, "99 yrs",
              "New Sale", unit_number="07-12")
    b = Trade(date(2024, 6, 1), "89", "11-15", 689, "2BR", 1_350_000, "99 yrs",
              "Resale", unit_number="07-12")
    assert a.pair_key == b.pair_key
    assert a.pair_key[0] == "unit"


def test_pair_key_distinguishes_units_in_same_band():
    # Without unit_number these would collide; with unit_number they don't.
    a = Trade(date(2020, 1, 1), "89", "06-10", 689, "2BR", 1_100_000, "99 yrs",
              "New Sale", unit_number="07-12")
    b = Trade(date(2024, 6, 1), "89", "06-10", 689, "2BR", 1_350_000, "99 yrs",
              "Resale", unit_number="08-12")
    assert a.pair_key != b.pair_key
