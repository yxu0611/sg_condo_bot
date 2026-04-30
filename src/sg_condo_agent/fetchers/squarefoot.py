import re
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

from ..condos import Condo
from ..models import Trade
from .csv_source import _infer_unit_type

PROJECT_URL_BASE = "https://www.squarefoot.com.sg/private-property/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    ),
    "Accept-Language": "en-SG,en;q=0.9",
}


def _floor_to_band(unit_label: str) -> str:
    m = re.search(r"#(\d+)", unit_label)
    if not m:
        return "?"
    f = int(m.group(1))
    lo = ((f - 1) // 5) * 5 + 1
    hi = lo + 4
    return f"{lo:02d}-{hi:02d}"


def _parse_money(s: str) -> int:
    return int(re.sub(r"[^\d]", "", s))


def _parse_area(s: str) -> int:
    return int(re.sub(r"[^\d]", "", s.split("sq")[0]))


def _parse_date(s: str) -> date:
    return datetime.strptime(s.strip(), "%b %Y").date().replace(day=1)


def parse_squarefoot_html(html: str) -> list[Trade]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.transaction-table")
    if table is None:
        return []
    out: list[Trade] = []
    for tr in table.select("tbody tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cells) < 6:
            continue
        date_s, block, unit, area_s, price_s, sale_type = cells[:6]
        area = _parse_area(area_s)
        out.append(
            Trade(
                contract_date=_parse_date(date_s),
                block=block.strip(),
                floor_range=_floor_to_band(unit),
                area_sqft=area,
                unit_type=_infer_unit_type(area),
                price_sgd=_parse_money(price_s),
                tenure="99 yrs",
                sale_type=sale_type.strip(),
            )
        )
    return out


def fetch_squarefoot(condo: Condo) -> list[Trade]:
    if not condo.squarefoot_slug:
        raise RuntimeError(
            f"condo '{condo.key}' has no squarefoot_slug — register one in condos.py "
            f"or use a different --source."
        )
    url = f"{PROJECT_URL_BASE}{condo.squarefoot_slug}"
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return parse_squarefoot_html(r.text)
