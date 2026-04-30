from datetime import date
from pathlib import Path

import pytest
import requests

from sg_condo_agent.condos import Condo
from sg_condo_agent.fetchers.squarefoot import (
    PROJECT_URL_PATTERNS,
    fetch_squarefoot,
    parse_squarefoot_html,
)

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


def _condo_with_slug() -> Condo:
    return Condo(
        key="x",
        name="X",
        ura_project_name="X",
        squarefoot_slug="x-residences",
    )


def test_fetch_squarefoot_walks_url_patterns_until_one_yields(monkeypatch):
    """First two URLs 404, third one returns the fixture HTML — fetcher
    must keep walking until a pattern matches, not give up after pattern 1.
    """
    class _R:
        def __init__(self, status_code: int, text: str = ""):
            self.status_code = status_code
            self.text = text

        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError(f"{self.status_code}")

    seen: list[str] = []
    fixture_html = FIXTURE.read_text()

    def fake_get(url, headers=None, timeout=None):  # noqa: ARG001
        seen.append(url)
        if len(seen) < 3:
            return _R(404)
        return _R(200, fixture_html)

    monkeypatch.setattr(requests, "get", fake_get)
    trades = fetch_squarefoot(_condo_with_slug())
    assert len(trades) == 3
    assert len(seen) == 3
    assert all("x-residences" in u for u in seen)


def test_fetch_squarefoot_raises_clear_error_when_all_404(monkeypatch):
    def boom(url, headers=None, timeout=None):  # noqa: ARG001
        raise requests.HTTPError("404")

    monkeypatch.setattr(requests, "get", boom)
    with pytest.raises(RuntimeError, match="restructured"):
        fetch_squarefoot(_condo_with_slug())


def test_fetch_squarefoot_requires_slug():
    no_slug = Condo(key="x", name="X", ura_project_name="X")
    with pytest.raises(RuntimeError, match="squarefoot_slug"):
        fetch_squarefoot(no_slug)


def test_url_patterns_cover_known_layouts():
    # Sanity check: registry must include the original /private-property/ path.
    assert any("/private-property/" in p for p in PROJECT_URL_PATTERNS)
