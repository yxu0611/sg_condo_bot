import re
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

from ..condos import Condo
from ..models import Trade
from .csv_source import _infer_unit_type

# SquareFoot restructured its URL scheme over time. Try each pattern in
# turn so a slug registered against an old layout still has a chance.
PROJECT_URL_PATTERNS = (
    "https://www.squarefoot.com.sg/private-property/{slug}",
    "https://www.squarefoot.com.sg/condominium/{slug}",
    "https://www.squarefoot.com.sg/property/{slug}",
)
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
    last_err: "Exception | None" = None
    for pattern in PROJECT_URL_PATTERNS:
        url = pattern.format(slug=condo.squarefoot_slug)
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
        except requests.RequestException as e:
            last_err = e
            continue
        trades = parse_squarefoot_html(r.text)
        if trades:
            return trades
    raise RuntimeError(
        "SquareFoot project page returned no transactions on any known URL "
        "pattern. The site restructured its public listings in 2025; prefer "
        "--source edgeprop or --source har."
    ) from last_err
