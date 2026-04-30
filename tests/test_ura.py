import pytest
import requests

from sg_condo_agent.condos import get
from sg_condo_agent.fetchers import ura as ura_mod
from sg_condo_agent.fetchers.ura import ENDPOINTS, fetch_ura, parse_ura_json

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


def test_fetch_ura_tries_each_endpoint_and_raises_with_migration_hint(monkeypatch):
    """All known URA hosts now 404 — fetcher must walk every endpoint and
    surface a clear migration hint instead of bare HTTPError."""
    calls: list[str] = []

    def boom(url, params=None, headers=None, timeout=None):  # noqa: ARG001
        calls.append(url)
        raise requests.HTTPError("404")

    monkeypatch.setattr(requests, "get", boom)

    with pytest.raises(RuntimeError, match="realEstateIIWeb"):
        fetch_ura(get("florence"))

    assert calls == list(ENDPOINTS)


def test_fetch_ura_returns_trades_when_first_endpoint_responds(monkeypatch):
    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return PAYLOAD

    def ok(url, params=None, headers=None, timeout=None):  # noqa: ARG001
        return FakeResp()

    monkeypatch.setattr(requests, "get", ok)
    trades = fetch_ura(get("florence"))
    assert len(trades) == 1  # filtered to the named project
