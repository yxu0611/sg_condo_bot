import json
from datetime import datetime
from importlib.resources import files
from statistics import median
from string import Template
from typing import Optional

from .condos import Condo
from .pairing import Classified


def _row_dict(c: Classified) -> dict:
    t = c.trade
    unit_label = f"{t.block} #{t.unit_number}" if t.unit_number else t.floor_range
    return {
        "contract_date": t.contract_date.isoformat(),
        "block": t.block,
        "unit_number": t.unit_number,
        "unit_label": unit_label,
        "floor_range": t.floor_range,
        "area_sqft": t.area_sqft,
        "unit_type": t.unit_type,
        "price_sgd": t.price_sgd,
        "psf": round(t.psf, 1),
        "tenure": t.tenure,
        "sale_type": t.sale_type,
        "status": c.status,
        "gross_profit": c.gross_profit,
        "buy_price": c.buy.price_sgd if c.buy else None,
        "buy_date": c.buy.contract_date.isoformat() if c.buy else None,
        "holding_years": round(c.holding_years, 2) if c.holding_years else None,
        "annualized_return": round(c.annualized_return, 4) if c.annualized_return else None,
    }


def render_html(
    classified: list[Classified],
    *,
    source: str,
    condo: Optional[Condo] = None,
) -> str:
    rows = [_row_dict(c) for c in classified]
    pls = [r["gross_profit"] for r in rows if r["gross_profit"] is not None]
    psfs = [r["psf"] for r in rows]

    counts = {"profitable": 0, "unprofitable": 0, "breakeven": 0, "no_prior": 0}
    for r in rows:
        counts[r["status"]] += 1

    tpl_text = (files("sg_condo_agent") / "template.html").read_text(encoding="utf-8")
    tpl = Template(tpl_text)
    name = condo.name if condo else "SG Condo"
    subtitle = condo.subtitle if condo else ""
    return tpl.safe_substitute(
        condo_name=name,
        condo_subtitle=subtitle,
        source=source,
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        count=len(rows),
        profitable=counts["profitable"],
        unprofitable=counts["unprofitable"],
        breakeven=counts["breakeven"],
        no_prior=counts["no_prior"],
        total_pl=f"{sum(pls):,}" if pls else "0",
        median_psf=f"{median(psfs):,.0f}" if psfs else "—",
        payload=json.dumps(rows),
    )
