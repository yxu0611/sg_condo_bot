import re
from datetime import date, datetime
from typing import Optional

import requests

from ..condos import Condo
from ..models import Trade
from .csv_source import _infer_unit_type

ENDPOINT = "https://www.ura.gov.sg/realEstateIIWeb/transaction/searchByProject.action"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    ),
    "Accept": "application/json,text/javascript,*/*;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
}


def _floor_band(level: str) -> str:
    return level.strip().replace(" to ", "-").replace(" TO ", "-")


def _parse_date(s: str) -> date:
    for fmt in ("%b-%y", "%b %y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unparsed URA date: {s!r}")


def parse_ura_json(payload: dict, project_filter: Optional[str] = None) -> list[Trade]:
    """Defensive: walk plausible keys for the transaction list.

    If ``project_filter`` is given, only rows whose ``projectName`` contains
    it (case-insensitive) are kept.
    """
    rows = (
        payload.get("transactionList")
        or payload.get("transactions")
        or (payload.get("result") or {}).get("transactionList")
        or []
    )
    needle = project_filter.upper() if project_filter else None
    out: list[Trade] = []
    for r in rows:
        if needle and needle not in str(r.get("projectName", "")).upper():
            continue
        area_raw = str(r.get("area") or r.get("areaSqft") or "0")
        area = int(re.sub(r"[^\d]", "", area_raw) or 0)
        if not area:
            continue
        price_raw = str(r.get("price") or r.get("transactedPrice") or "0")
        price = int(re.sub(r"[^\d]", "", price_raw) or 0)
        out.append(
            Trade(
                contract_date=_parse_date(str(r.get("contractDate") or r.get("saleDate"))),
                block=str(r.get("block") or "-").strip() or "-",
                floor_range=_floor_band(str(r.get("floorLevel") or r.get("floorRange") or "")),
                area_sqft=area,
                unit_type=_infer_unit_type(area),
                price_sgd=price,
                tenure=str(r.get("tenure") or "99 yrs"),
                sale_type=str(r.get("typeOfSale") or r.get("saleType") or "Resale"),
            )
        )
    return out


def fetch_ura(condo: Condo) -> list[Trade]:
    r = requests.get(
        ENDPOINT,
        params={"projectName": condo.ura_project_name},
        headers=HEADERS,
        timeout=20,
    )
    r.raise_for_status()
    return parse_ura_json(r.json(), project_filter=condo.ura_project_name)
