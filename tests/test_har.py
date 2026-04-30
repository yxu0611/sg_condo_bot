from pathlib import Path

import pytest

from sg_condo_agent.condos import get
from sg_condo_agent.fetchers.har import fetch_har
from sg_condo_agent.fetchers import fetch

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "parktown_sample.har"
PARTIAL = FIXTURES / "parktown_partial.har"


def test_har_extracts_sale_transactions():
    parktown = get("parktown")
    trades = fetch_har(SAMPLE, parktown)
    # 4 trades for asset 295529 (the unrelated assetid 999999 entry must be skipped)
    assert len(trades) == 4
    assert all(t.unit_number for t in trades)
    assert {t.unit_type for t in trades} == {"2BR", "3BR", "4BR+"}


def test_har_filters_to_condo_assetid():
    # Without a condo, all entries (including the unrelated assetid) come through.
    rows = fetch_har(SAMPLE, condo=None)
    assert len(rows) == 5  # 2+2 parktown + 1 unrelated


def test_har_partial_coverage_warning(capsys):
    parktown = get("parktown")
    trades = fetch_har(PARTIAL, parktown)
    captured = capsys.readouterr()
    assert len(trades) == 1
    assert "partial coverage" in captured.err
    assert "1158" in captured.err


def test_fetch_orchestrator_uses_har_when_provided():
    parktown = get("parktown")
    trades, used = fetch(parktown, source="har", har_path=SAMPLE)
    assert used == "har"
    assert len(trades) == 4


def test_auto_mode_prefers_har_when_path_given():
    # In 'auto', HAR comes first if har_path is supplied; otherwise it's skipped.
    parktown = get("parktown")
    trades, used = fetch(parktown, source="auto", har_path=SAMPLE)
    assert used == "har"


def test_har_source_pinned_without_path_raises_or_returns_empty():
    parktown = get("parktown")
    trades, used = fetch(parktown, source="har", har_path=None)
    assert trades == []
    assert used == "none"
