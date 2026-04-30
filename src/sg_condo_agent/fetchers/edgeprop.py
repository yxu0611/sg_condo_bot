"""EdgeProp transaction fetcher.

Calls the same backend that the EdgeProp project page uses. Cookies are
required (Cloudflare clearance + session); the cookie string is read from
the file pointed to by `EDGEPROP_COOKIE_FILE`. Cookies are never logged
and never embedded in source.

Each transaction includes a real unit number (e.g. ``#14-38``), which lets
us pair same-unit trades accurately rather than relying on URA's
floor-band heuristic.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..condos import Condo
from ..models import Trade
from .csv_source import _infer_unit_type

ENDPOINT = "https://www.edgeprop.sg/index.php"
PROJECT_REFERER_BASE = "https://www.edgeprop.sg/listing/apartment-condo/condominium/"
PAGE_LIMIT = 200
REQUEST_DELAY_SEC = 0.4  # be polite


def _load_cookie() -> str:
    path = os.environ.get("EDGEPROP_COOKIE_FILE")
    if not path:
        raise RuntimeError(
            "EDGEPROP_COOKIE_FILE not set. Save the Cookie header value to a "
            "file (e.g. /tmp/edgeprop_cookie.txt) and export "
            "EDGEPROP_COOKIE_FILE=<that path>."
        )
    text = Path(path).read_text().strip()
    if not text:
        raise RuntimeError(f"cookie file {path} is empty")
    return text


def _request_page(condo: Condo, page: int, limit: int, cookie: str) -> dict:
    if not condo.edgeprop_asset_id:
        raise RuntimeError(
            f"condo '{condo.key}' has no edgeprop_asset_id — register one in condos.py "
            f"or use a different --source."
        )
    referer = f"{PROJECT_REFERER_BASE}{condo.edgeprop_slug}" if condo.edgeprop_slug else PROJECT_REFERER_BASE
    qs = (
        f"option=com_mobile&task=tx&op=data&listing_type=sale"
        f"&assetid={condo.edgeprop_asset_id}&page={page}&limit={limit}"
    )
    req = urllib.request.Request(
        f"{ENDPOINT}?{qs}",
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/147.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
            "Cookie": cookie,
            "Referer": referer,
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


_BLOCK_RE = re.compile(r"^\s*(\w+)\s")
_UNIT_RE = re.compile(r"#(\d+-?\w*)")


def _parse_block(address: str) -> str:
    m = _BLOCK_RE.match(address or "")
    return m.group(1) if m else "-"


def _parse_unit(unit: str) -> Optional[str]:
    if not unit:
        return None
    m = _UNIT_RE.search(unit)
    return m.group(1) if m else None


def _floor_band(unit_number: Optional[str]) -> str:
    if not unit_number:
        return "?"
    m = re.match(r"(\d+)", unit_number)
    if not m:
        return "?"
    f = int(m.group(1))
    lo = ((f - 1) // 5) * 5 + 1
    hi = lo + 4
    return f"{lo:02d}-{hi:02d}"


def _bedrooms_to_unit_type(beds: int, area_sqft: int) -> str:
    if beds and beds > 0:
        return f"{beds}BR" if beds < 4 else "4BR+"
    return _infer_unit_type(area_sqft)


def parse_edgeprop_response(rows: list[dict]) -> list[Trade]:
    """Convert EdgeProp transaction rows to Trade objects."""
    out: list[Trade] = []
    for r in rows:
        ts = r.get("contract_date")
        if not ts:
            continue
        try:
            d = datetime.fromtimestamp(int(ts), tz=timezone.utc).date()
        except (TypeError, ValueError):
            continue
        unit_number = _parse_unit(str(r.get("unit") or ""))
        area = int(r.get("area_sqft") or 0)
        if not area:
            continue
        price = int(r.get("transacted_price") or 0)
        if not price:
            continue
        beds = int(r.get("bedrooms") or 0)
        out.append(
            Trade(
                contract_date=d,
                block=_parse_block(str(r.get("address") or "")),
                floor_range=_floor_band(unit_number),
                area_sqft=area,
                unit_type=_bedrooms_to_unit_type(beds, area),
                price_sgd=price,
                tenure=str(r.get("tenure") or "99 yrs"),
                sale_type=str(r.get("type_of_sale") or "Resale"),
                unit_number=unit_number,
            )
        )
    return out


def fetch_edgeprop(
    condo: Condo,
    cache_path: Optional[Path | str] = None,
    *,
    force: bool = False,
) -> list[Trade]:
    """Fetch all transactions for ``condo``, paginating until exhausted.

    Caches the parsed JSON pages to ``cache_path`` (default
    ``./.edgeprop_cache_<condo.key>.json``) so subsequent runs are free
    unless ``force``.
    """
    cache_path = (
        Path(cache_path)
        if cache_path
        else Path(f".edgeprop_cache_{condo.key}.json")
    )
    if cache_path.exists() and not force:
        rows = json.loads(cache_path.read_text())
        return parse_edgeprop_response(rows)

    cookie = _load_cookie()
    all_rows: list[dict] = []
    page = 1
    total: Optional[int] = None
    while True:
        payload = _request_page(condo, page, PAGE_LIMIT, cookie)
        if payload.get("status") != 1:
            raise RuntimeError(f"edgeprop returned status={payload.get('status')}")
        rows = payload.get("response") or []
        all_rows.extend(rows)
        if total is None:
            total = int(payload.get("total") or 0)
        print(f"[edgeprop] page {page}: +{len(rows)} (total so far {len(all_rows)}/{total})")
        if not rows or len(all_rows) >= (total or 0):
            break
        page += 1
        time.sleep(REQUEST_DELAY_SEC)

    cache_path.write_text(json.dumps(all_rows))
    print(f"[edgeprop] cached {len(all_rows)} rows → {cache_path}")
    return parse_edgeprop_response(all_rows)
