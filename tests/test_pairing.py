from datetime import date
from florence_agent.models import Trade
from florence_agent.pairing import classify


def _t(year, area, price, sale_type="Resale", floor="06-10"):
    return Trade(
        contract_date=date(year, 6, 1),
        block="-",
        floor_range=floor,
        area_sqft=area,
        unit_type="2BR",
        price_sgd=price,
        tenure="99 yrs",
        sale_type=sale_type,
    )


def test_no_prior_when_only_one_trade():
    [c] = classify([_t(2019, 689, 1_100_000, "New Sale")])
    assert c.status == "no_prior"
    assert c.gross_profit is None


def test_profitable_pair():
    rows = classify([
        _t(2019, 689, 1_100_000, "New Sale"),
        _t(2024, 689, 1_350_000, "Resale"),
    ])
    rows.sort(key=lambda r: r.trade.contract_date)
    assert rows[0].status == "no_prior"
    assert rows[1].status == "profitable"
    assert rows[1].gross_profit == 250_000
    assert rows[1].holding_years and round(rows[1].holding_years, 1) == 5.0


def test_unprofitable_pair():
    rows = classify([
        _t(2019, 915, 1_520_000, "New Sale"),
        _t(2023, 915, 1_470_000, "Resale"),
    ])
    rows.sort(key=lambda r: r.trade.contract_date)
    assert rows[1].status == "unprofitable"
    assert rows[1].gross_profit == -50_000


def test_separate_units_do_not_pair():
    a = _t(2019, 689, 1_100_000, "New Sale", floor="06-10")
    b = _t(2024, 689, 1_350_000, "Resale", floor="11-15")
    rows = classify([a, b])
    assert all(r.status == "no_prior" for r in rows)


def test_two_new_sales_never_pair_each_other():
    # Same bucket but neither is a Resale/Sub Sale: both stay no_prior.
    rows = classify([
        _t(2019, 689, 1_100_000, "New Sale"),
        _t(2020, 689, 1_200_000, "New Sale"),
    ])
    assert all(r.status == "no_prior" for r in rows)


def test_resale_uses_fifo_buy_each_buy_once():
    # Two New Sales then a single Resale → Resale pairs with earliest New Sale,
    # the second New Sale stays no_prior (it represents a different unit).
    rows = classify([
        _t(2019, 689, 1_100_000, "New Sale"),
        _t(2020, 689, 1_200_000, "New Sale"),
        _t(2024, 689, 1_350_000, "Resale"),
    ])
    rows.sort(key=lambda r: r.trade.contract_date)
    assert rows[0].status == "no_prior"
    assert rows[1].status == "no_prior"
    assert rows[2].status == "profitable"
    assert rows[2].buy.price_sgd == 1_100_000  # FIFO: earliest unused buy
    assert rows[2].gross_profit == 250_000


def test_two_resales_consume_two_buys():
    rows = classify([
        _t(2019, 689, 1_100_000, "New Sale"),
        _t(2020, 689, 1_200_000, "New Sale"),
        _t(2023, 689, 1_300_000, "Resale"),
        _t(2024, 689, 1_400_000, "Resale"),
    ])
    rows.sort(key=lambda r: r.trade.contract_date)
    # Resale 2023 ↔ NewSale 2019 (oldest unused), Resale 2024 ↔ NewSale 2020.
    assert rows[2].status == "profitable" and rows[2].buy.price_sgd == 1_100_000
    assert rows[3].status == "profitable" and rows[3].buy.price_sgd == 1_200_000
