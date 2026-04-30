"""Parse EdgeProp transaction responses out of a saved HAR file.

Chrome DevTools (Network panel → right-click → Save all as HAR) captures
every XHR the browser made, including the EdgeProp ``index.php?task=tx``
endpoint that powers the project transactions table. Because cookies are
already attached by the browser, the HAR contains real response bodies —
we don't need ``EDGEPROP_COOKIE_FILE`` to reuse them.

Workflow for full coverage:
    1. Open the project's EdgeProp page in a browser, click "View all
       transactions", and scroll / paginate until every page is loaded.
    2. DevTools → Network → right-click any row → "Save all as HAR with
       content".
    3. ``sg-condo-agent --condo <key> --source har --har <path>``.

If the HAR only contains a subset of pages, this fetcher returns whatever
it finds and prints a coverage warning so the caller knows.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional

from ..condos import Condo
from ..models import Trade
from .edgeprop import parse_edgeprop_response


_TX_URL_RE = re.compile(r"task=tx.*listing_type=sale", re.I)
_PAGE_RE = re.compile(r"[?&]page=(\d+)")
_ASSETID_RE = re.compile(r"[?&]assetid=(\d+)")


def _extract_sale_pages(har_path: Path, condo: Optional[Condo]) -> tuple[list[dict], Optional[int], list[int]]:
    """Walk the HAR, collect transaction-page payloads.

    Returns (rows, declared_total, page_numbers_seen). When ``condo`` has an
    edgeprop_asset_id set, only pages matching that asset are kept (HARs
    sometimes mix multiple projects when the user browsed several).
    """
    target_asset = str(condo.edgeprop_asset_id) if condo and condo.edgeprop_asset_id else None
    har = json.loads(Path(har_path).read_text(encoding="utf-8"))
    # Keyed on (asset_id, page) so the same page-1 across multiple projects
    # in a single HAR doesn't collide.
    pages: dict[tuple[str, int], list[dict]] = {}
    declared_total: Optional[int] = None
    for e in har.get("log", {}).get("entries", []):
        req = e.get("request") or {}
        url = req.get("url", "")
        if not _TX_URL_RE.search(url):
            continue
        m_asset = _ASSETID_RE.search(url)
        asset = m_asset.group(1) if m_asset else "?"
        if target_asset and asset != target_asset:
            continue
        body = ((e.get("response") or {}).get("content") or {}).get("text") or ""
        if not body:
            continue
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            continue
        rows = payload.get("response") or []
        if declared_total is None:
            t = payload.get("total")
            if t is not None:
                try:
                    declared_total = int(t)
                except (TypeError, ValueError):
                    pass
        m_page = _PAGE_RE.search(url)
        page = int(m_page.group(1)) if m_page else len(pages) + 1
        pages.setdefault((asset, page), rows)

    flat: list[dict] = []
    for k in sorted(pages):
        flat.extend(pages[k])
    page_numbers = sorted({p for _, p in pages})
    return flat, declared_total, page_numbers


def _dedup(rows: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    out: list[dict] = []
    for r in rows:
        k = (r.get("contract_date"), r.get("unit"), r.get("transacted_price"), r.get("area_sqft"))
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def fetch_har(har_path: Path | str, condo: Optional[Condo] = None) -> list[Trade]:
    """Load EdgeProp sale transactions from a saved HAR file."""
    rows, declared_total, page_numbers = _extract_sale_pages(Path(har_path), condo)
    rows = _dedup(rows)
    trades = parse_edgeprop_response(rows)

    if declared_total and len(trades) < declared_total:
        coverage = (len(trades) / declared_total) * 100
        missing = declared_total - len(trades)
        msg = (
            f"[har] partial coverage: parsed {len(trades)} of {declared_total} "
            f"transactions ({coverage:.1f}%), missing {missing}. "
            f"Pages captured: {page_numbers}. "
            "To get the full set, open the EdgeProp transactions tab, scroll "
            "or paginate until every row is loaded, then re-save the HAR."
        )
        print(msg, file=sys.stderr)

    return trades
