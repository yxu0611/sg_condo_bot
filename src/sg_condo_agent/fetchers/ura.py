import re
from datetime import date, datetime
from typing import Optional

import requests

from ..condos import Condo
from ..models import Trade
from .csv_source import _infer_unit_type

# Legacy public AJAX endpoints; both ``www`` and ``eservice`` subdomains
# are tried because URA migrates services between them. As of 2026-04 the
# whole ``realEstateIIWeb`` app has been retired in favour of the
# pmiResidentialTransactionSearch HTML form, which gates results behind
# SingPass — so this fetcher is best-effort and ``parse_ura_json`` is
# the durable piece (also reused for HAR/test payloads).
ENDPOINTS = (
    "https://www.ura.gov.sg/realEstateIIWeb/transaction/searchByProject.action",
    "https://eservice.ura.gov.sg/realEstateIIWeb/transaction/searchByProject.action",
)
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
    """Try each known URA AJAX host in turn.

    Raises ``RuntimeError`` with a clear migration hint if none answer
    with parseable JSON — typical now that ``realEstateIIWeb`` is retired.
    Use ``--source csv`` (REALIS export) or ``--source har`` (saved
    EdgeProp session) instead.
    """
    last_err: Optional[Exception] = None
    for url in ENDPOINTS:
        try:
            r = requests.get(
                url,
                params={"projectName": condo.ura_project_name},
                headers=HEADERS,
                timeout=20,
            )
            r.raise_for_status()
            return parse_ura_json(r.json(), project_filter=condo.ura_project_name)
        except (requests.RequestException, ValueError) as e:
            last_err = e
            continue
    raise RuntimeError(
        "URA realEstateIIWeb endpoint did not return JSON from any known host. "
        "It was retired in favour of pmiResidentialTransactionSearch (login-gated). "
        "Use --source csv with a REALIS CSV export, or --source har with a saved "
        "EdgeProp transactions HAR."
    ) from last_err
