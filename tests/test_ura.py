from sg_condo_agent.fetchers.ura import parse_ura_json

PAYLOAD = {
    "transactionList": [
        {
            "projectName": "FLORENCE RESIDENCES",
            "block": "80",
            "floorLevel": "06 to 10",
            "area": "689",
            "price": "1350000",
            "contractDate": "Jun-24",
            "tenure": "99 yrs lease commencing from 2018",
            "typeOfSale": "Resale",
        },
        {"projectName": "Other Condo", "area": "1000", "price": "2000000",
         "contractDate": "Jun-24", "floorLevel": "01 to 05"},
    ]
}


def test_parse_filters_to_named_project():
    trades = parse_ura_json(PAYLOAD, project_filter="FLORENCE RESIDENCES")
    assert len(trades) == 1
    assert trades[0].block == "80"
    assert trades[0].price_sgd == 1_350_000
    assert trades[0].floor_range == "06-10"


def test_parse_no_filter_returns_all():
    trades = parse_ura_json(PAYLOAD)
    assert len(trades) == 2
