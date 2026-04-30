"""Gradio app — interactive transaction explorer for any registered SG condo.

Run via the ``sg-condo-share`` console script. Pass ``--condo <key>`` to pick
which project to load (defaults to ``florence``). Falls back through the
fetcher chain just like the CLI.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import gradio as gr
import pandas as pd
import plotly.express as px

from .condos import Condo, get, list_keys
from .fetchers import fetch
from .pairing import classify
from .render import _row_dict


STATUS_COLORS = {
    "profitable": "#0a7d2e",
    "unprofitable": "#b02828",
    "breakeven": "#888888",
    "no_prior": "#bbbbbb",
}


def _load_dataframe(condo: Condo, source: str, csv_path: Path | None, har_path: Path | None = None) -> tuple[pd.DataFrame, dict, str]:
    trades, used = fetch(condo, source, csv_path, har_path)
    if not trades:
        raise RuntimeError(f"no trades found for {condo.name} from source={source}")
    classified = classify(trades)
    rows = [_row_dict(c) for c in classified]
    df = pd.DataFrame(rows)
    df["contract_date"] = pd.to_datetime(df["contract_date"])

    counts = Counter(df["status"])
    paired = df[df["gross_profit"].notna()]
    profitable = paired[paired["gross_profit"] > 0]
    unprofitable = paired[paired["gross_profit"] < 0]

    summary = {
        "total_trades": len(df),
        "unique_units": df["unit_number"].dropna().nunique(),
        "date_min": df["contract_date"].min().strftime("%Y-%m"),
        "date_max": df["contract_date"].max().strftime("%Y-%m"),
        "profitable": int(counts.get("profitable", 0)),
        "unprofitable": int(counts.get("unprofitable", 0)),
        "breakeven": int(counts.get("breakeven", 0)),
        "no_prior": int(counts.get("no_prior", 0)),
        "total_pl": int(paired["gross_profit"].sum()) if len(paired) else 0,
        "median_profit": int(profitable["gross_profit"].median()) if len(profitable) else 0,
        "median_holding": float(profitable["holding_years"].median()) if len(profitable) else 0,
        "median_psf": int(df["psf"].median()),
        "hit_rate": (len(profitable) / len(paired) * 100) if len(paired) else 0,
    }
    if len(profitable):
        top = profitable.loc[profitable["gross_profit"].idxmax()]
        summary["top_unit"] = top["unit_label"]
        summary["top_profit"] = int(top["gross_profit"])
        summary["top_years"] = float(top["holding_years"])
        summary["top_ann"] = float(top["annualized_return"]) * 100
    if len(unprofitable):
        worst = unprofitable.loc[unprofitable["gross_profit"].idxmin()]
        summary["worst_unit"] = worst["unit_label"]
        summary["worst_loss"] = int(worst["gross_profit"])
        summary["worst_years"] = float(worst["holding_years"])
    return df, summary, used


def _conclusions_md(condo: Condo, s: dict) -> str:
    paired_total = s["profitable"] + s["unprofitable"] + s["breakeven"]
    parts = [
        f"## Summary — {condo.name}",
        "",
        condo.subtitle,
        "",
        f"**{s['total_trades']:,}** sale records, **{s['unique_units']:,}** distinct units, "
        f"{s['date_min']} → {s['date_max']}.",
        "",
        "### Resale economics",
        f"- Paired Resale / Sub-Sale records: **{paired_total:,}** "
        f"(profit: {s['profitable']:,} · loss: {s['unprofitable']:,} · breakeven: {s['breakeven']:,}).",
        f"- Hit rate: **{s['hit_rate']:.1f}%** of paired trades came out profitable.",
        f"- Median profit **S${s['median_profit']:,}** over **{s['median_holding']:.1f}** years.",
        "",
        "### Aggregate",
        f"- Total gross P/L: **S${s['total_pl']:,}** (~S${s['total_pl']/1_000_000:.1f}M). "
        "Excludes stamp duty / agent / legal.",
        "",
        "### Notable",
    ]
    if "top_unit" in s:
        parts.append(
            f"- **Best gain**: unit `{s['top_unit']}`, +S${s['top_profit']:,}, "
            f"held {s['top_years']:.1f} yrs (annualized {s['top_ann']:.1f}%)"
        )
    if "worst_unit" in s:
        parts.append(
            f"- **Worst loss**: unit `{s['worst_unit']}`, "
            f"-S${abs(s['worst_loss']):,}, held {s['worst_years']:.1f} yrs"
        )
    parts += [
        "",
        "### Notes",
        f"- {s['no_prior']:,} trades labelled `no_prior` are typically New Sale "
        "records with no follow-on resale yet — not missing data.",
        "- Pairing prefers the source's real unit number when available; otherwise "
        "falls back to the URA-CSV (block, floor band, area, unit type) heuristic.",
        "- P/L is **gross** — net profit is typically ~10-15% lower after BSD / "
        "ABSD / SSD / agent / legal fees, depending on holder type.",
    ]
    return "\n".join(parts)


def _filtered(df: pd.DataFrame, status: str, search: str) -> pd.DataFrame:
    out = df
    if status and status != "All":
        out = out[out["status"] == status]
    if search:
        q = search.strip().lower()
        if q:
            mask = (
                out["unit_label"].str.lower().str.contains(q, na=False)
                | out["unit_type"].str.lower().str.contains(q, na=False)
                | out["sale_type"].str.lower().str.contains(q, na=False)
                | out["area_sqft"].astype(str).str.contains(q, na=False)
            )
            out = out[mask]
    cols = [
        "contract_date", "unit_label", "unit_type", "area_sqft",
        "psf", "price_sgd", "sale_type",
        "holding_years", "buy_price", "gross_profit",
        "annualized_return", "status",
    ]
    out = out[cols].copy()
    out["contract_date"] = out["contract_date"].dt.strftime("%Y-%m-%d")
    return out.sort_values("contract_date", ascending=False)


def _build_scatter(df: pd.DataFrame, title: str):
    fig = px.scatter(
        df, x="contract_date", y="psf", color="status",
        color_discrete_map=STATUS_COLORS,
        hover_data={
            "unit_label": True, "unit_type": True, "area_sqft": True,
            "price_sgd": ":,.0f", "sale_type": True,
            "gross_profit": ":,.0f", "status": True,
            "contract_date": False, "psf": ":,.0f",
        },
        title=title,
    )
    fig.update_traces(marker=dict(size=7, line=dict(width=0.3, color="#333"), opacity=0.85))
    fig.update_layout(
        height=400, margin=dict(t=40, r=12, b=40, l=60),
        xaxis_title="Contract date", yaxis_title="S$ / sqft",
    )
    return fig


def build_app(condo: Condo, source: str = "auto", csv_path: Path | None = None,
              har_path: Path | None = None) -> gr.Blocks:
    df, summary, used = _load_dataframe(condo, source, csv_path, har_path)
    scatter = _build_scatter(df, "PSF over time, colored by profit status")

    css = """
    .kpi { background:white; border:1px solid #e3e3e3; border-radius:8px; padding:12px 16px; }
    .kpi .label { font-size:11px; color:#888; text-transform:uppercase; letter-spacing:.04em; }
    .kpi .value { font-size:20px; font-weight:600; margin-top:4px; font-variant-numeric: tabular-nums; }
    """

    def kpi(label: str, value: str, color: str = "#1a1a1a") -> str:
        return f'<div class="kpi"><div class="label">{label}</div><div class="value" style="color:{color}">{value}</div></div>'

    title = f"{condo.name} — Transaction Report"
    with gr.Blocks(title=title, css=css, theme=gr.themes.Soft()) as app:
        gr.Markdown(
            f"# {title}\n"
            f"*{condo.subtitle}*  \n"
            f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} from {used}"
        )

        with gr.Row():
            gr.HTML(kpi("Total trades", f"{summary['total_trades']:,}"))
            gr.HTML(kpi("Profitable", f"{summary['profitable']:,}", "#0a7d2e"))
            gr.HTML(kpi("Unprofitable", f"{summary['unprofitable']:,}", "#b02828"))
            gr.HTML(kpi("No prior", f"{summary['no_prior']:,}"))
            gr.HTML(kpi("Hit rate", f"{summary['hit_rate']:.1f}%", "#0a7d2e"))
            gr.HTML(kpi("Total gross P/L", f"S${summary['total_pl']:,}", "#0a7d2e"))
            gr.HTML(kpi("Median PSF", f"S${summary['median_psf']:,}"))

        gr.Markdown(_conclusions_md(condo, summary))

        gr.Plot(scatter, label="Price per sqft over time")

        gr.Markdown("### Transactions")
        with gr.Row():
            status_filter = gr.Radio(
                choices=["All", "profitable", "unprofitable", "breakeven", "no_prior"],
                value="All", label="Status filter", scale=3,
            )
            search_box = gr.Textbox(
                label="Search (unit / bed / sqft / sale type)",
                placeholder="e.g. 03-12  or  3BR  or  Resale", scale=2,
            )
        table = gr.DataFrame(
            value=_filtered(df, "All", ""),
            interactive=False, wrap=False, max_height=520,
        )
        status_filter.change(lambda s, q: _filtered(df, s, q), [status_filter, search_box], table)
        search_box.change(lambda s, q: _filtered(df, s, q), [status_filter, search_box], table)

        gr.Markdown(
            "---\n"
            "*Profit/Loss figures are **gross** — they exclude buyer's stamp duty (BSD), "
            "additional stamp duty (ABSD), seller's stamp duty (SSD), agent commission "
            "and legal fees. \"Same unit\" pairing uses the source's actual unit number "
            "when present, otherwise the (block, floor band, area, unit type) heuristic; "
            "Resale / Sub-Sale trades match FIFO against the earliest unused prior trade "
            "in the same physical unit. Past performance does not guarantee future "
            "returns; this report is informational and not investment advice.*"
        )
    return app


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="sg-condo-share",
        description="Launch a Gradio explorer for an SG condo's transactions.",
    )
    p.add_argument(
        "--condo",
        default="florence",
        help=f"Registered condo key ({', '.join(list_keys())}) or free-form project name.",
    )
    p.add_argument("--source", default="auto",
                   choices=["auto", "edgeprop", "har", "csv", "squarefoot", "ura"])
    p.add_argument("--csv", type=Path, default=None)
    p.add_argument("--har", type=Path, default=None,
                   help="Chrome DevTools HAR export with EdgeProp transaction calls captured.")
    p.add_argument("--share", action="store_true", help="Expose a public Gradio link.")
    p.add_argument("--server-name", default="0.0.0.0")
    args = p.parse_args(argv)

    condo = get(args.condo)
    try:
        app = build_app(condo, args.source, args.csv, args.har)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 2
    app.launch(share=args.share, server_name=args.server_name, show_api=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
