import json
import re
from datetime import date

from sg_condo_agent.condos import get
from sg_condo_agent.models import Trade
from sg_condo_agent.pairing import classify
from sg_condo_agent.render import render_html


def _seed():
    return [
        Trade(date(2019, 3, 1), "-", "06-10", 689, "2BR", 1_100_000, "99 yrs", "New Sale"),
        Trade(date(2024, 6, 1), "-", "06-10", 689, "2BR", 1_350_000, "99 yrs", "Resale"),
    ]


def test_render_returns_html_with_doctype():
    html = render_html(classify(_seed()), source="csv", condo=get("florence"))
    assert html.lstrip().lower().startswith("<!doctype html>")


def test_render_embeds_trade_json():
    html = render_html(classify(_seed()), source="csv", condo=get("florence"))
    m = re.search(r'id="trades-data"[^>]*>(.+?)</script>', html, re.S)
    assert m, "trades-data script not found"
    payload = json.loads(m.group(1))
    assert len(payload) == 2
    assert any(row["status"] == "profitable" for row in payload)


def test_render_includes_summary_counts():
    html = render_html(classify(_seed()), source="csv", condo=get("florence"))
    assert "Total trades" in html
    assert ">2<" in html


def test_render_uses_condo_name_in_title():
    html = render_html(classify(_seed()), source="csv", condo=get("florence"))
    assert "The Florence Residences" in html


def test_render_works_for_adhoc_condo():
    html = render_html(classify(_seed()), source="csv", condo=get("Some New Condo"))
    assert "Some New Condo" in html
