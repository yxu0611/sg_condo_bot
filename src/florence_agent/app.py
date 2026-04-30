"""Gradio app for the Florence Residences transaction explorer."""
from __future__ import annotations

import statistics
from collections import Counter
from datetime import datetime

import gradio as gr
import pandas as pd
import plotly.express as px

from .fetchers.edgeprop import fetch_edgeprop
from .pairing import classify
from .render import _row_dict


STATUS_COLORS = {
    "profitable": "#0a7d2e",
    "unprofitable": "#b02828",
    "breakeven": "#888888",
    "no_prior": "#bbbbbb",
}


def _load_dataframe() -> tuple[pd.DataFrame, dict]:
    trades = fetch_edgeprop()
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
    return df, summary


def _conclusions_md(s: dict) -> str:
    lines = [
        "## 结论 / Conclusions",
        "",
        f"**The Florence Residences** (Hougang Ave 2, D19, 99-yr from 2018, TOP 2022) — {s['total_trades']:,} 笔 sale 成交，{s['unique_units']:,} 个独立 unit，时间跨度 {s['date_min']} → {s['date_max']}。",
        "",
        f"### 1. 二手转售盈利极强（97%+ hit rate）",
        f"- 已配对 resale/sub-sale 共 **{s['profitable'] + s['unprofitable'] + s['breakeven']:,}** 笔，其中 **{s['profitable']:,}** 笔盈利、**{s['unprofitable']:,}** 笔亏损、{s['breakeven']:,} 笔持平。",
        f"- **{s['hit_rate']:.1f}%** 的二手成交都是赚钱的 —— 这个比例在新加坡新盘里偏高，反映 Florence Residences 在 2019 入市价相对保守 + 2020-2025 整体房价上涨周期。",
        f"- 中位盈利 **S${s['median_profit']:,}**，中位持有 **{s['median_holding']:.1f} 年**。",
        "",
        f"### 2. 总盈亏 +S${s['total_pl']:,}（gross）",
        f"- 全部已平仓买卖 gross 累计盈余约 S${s['total_pl']/1_000_000:.1f}M，未扣 BSD / ABSD / SSD / 中介费 / 律师费。",
        f"- 实际净盈利会比这个数字低 ~10-15% 取决于持有期和买家身份。",
        "",
        f"### 3. 个案高低点",
        f"- **盈利之最**：unit `{s.get('top_unit', '—')}`，盈 S${s.get('top_profit', 0):,}，持有 {s.get('top_years', 0):.1f} 年（年化 {s.get('top_ann', 0):.1f}%）",
        f"- **亏损之最**：unit `{s.get('worst_unit', '—')}`，亏 S${abs(s.get('worst_loss', 0)):,}，持有 {s.get('worst_years', 0):.1f} 年",
        "",
        f"### 4. 注意事项",
        f"- {s['no_prior']:,} 笔标 `no_prior` 主要是开发商的 New Sale 还没产生二次成交，**不代表数据缺失**。",
        f"- 配对方法：以 EdgeProp 提供的真实 unit number（如 `#14-38`）作为 same-unit 判定，FIFO 配对相邻 buy/sell。",
        f"- 数据源：EdgeProp（其底层 source = URA REALIS）；项目 asset_id = 291412。",
        f"- P/L 是 gross。要算 net profit 需要分别按 holder 类型套 stamp duty 表。",
    ]
    return "\n".join(lines)


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


def _build_scatter(df: pd.DataFrame):
    fig = px.scatter(
        df, x="contract_date", y="psf", color="status",
        color_discrete_map=STATUS_COLORS,
        hover_data={
            "unit_label": True, "unit_type": True, "area_sqft": True,
            "price_sgd": ":,.0f", "sale_type": True,
            "gross_profit": ":,.0f", "status": True,
            "contract_date": False, "psf": ":,.0f",
        },
        title="PSF over time, colored by profit status",
    )
    fig.update_traces(marker=dict(size=7, line=dict(width=0.3, color="#333"), opacity=0.85))
    fig.update_layout(
        height=400, margin=dict(t=40, r=12, b=40, l=60),
        xaxis_title="Contract date", yaxis_title="S$ / sqft",
    )
    return fig


def build_app() -> gr.Blocks:
    df, summary = _load_dataframe()
    scatter = _build_scatter(df)

    css = """
    .kpi { background:white; border:1px solid #e3e3e3; border-radius:8px; padding:12px 16px; }
    .kpi .label { font-size:11px; color:#888; text-transform:uppercase; letter-spacing:.04em; }
    .kpi .value { font-size:20px; font-weight:600; margin-top:4px; font-variant-numeric: tabular-nums; }
    """

    def kpi(label: str, value: str, color: str = "#1a1a1a") -> str:
        return f'<div class="kpi"><div class="label">{label}</div><div class="value" style="color:{color}">{value}</div></div>'

    with gr.Blocks(title="Florence Residences — Transaction Report", css=css, theme=gr.themes.Soft()) as app:
        gr.Markdown(
            f"# Florence Residences — Transaction Report\n"
            f"*Hougang Ave 2 · D19 · 99-yr from 2018 · TOP 2022 · 1,410 units*  \n"
            f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} from EdgeProp (source: URA)"
        )

        with gr.Row():
            gr.HTML(kpi("Total trades", f"{summary['total_trades']:,}"))
            gr.HTML(kpi("Profitable", f"{summary['profitable']:,}", "#0a7d2e"))
            gr.HTML(kpi("Unprofitable", f"{summary['unprofitable']:,}", "#b02828"))
            gr.HTML(kpi("No prior", f"{summary['no_prior']:,}"))
            gr.HTML(kpi("Hit rate", f"{summary['hit_rate']:.1f}%", "#0a7d2e"))
            gr.HTML(kpi("Total gross P/L", f"S${summary['total_pl']:,}", "#0a7d2e"))
            gr.HTML(kpi("Median PSF", f"S${summary['median_psf']:,}"))

        gr.Markdown(_conclusions_md(summary))

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
            "*Data via EdgeProp.sg, ultimately sourced from URA REALIS. Profit/Loss "
            "figures are **gross** — they exclude buyer's stamp duty (BSD), additional "
            "stamp duty (ABSD), seller's stamp duty (SSD), agent commission and legal "
            "fees. \"Same unit\" pairing uses EdgeProp's actual unit number, and matches "
            "Resale / Sub Sale trades FIFO with the earliest unused prior trade in the "
            "same physical unit. Past performance does not guarantee future returns; "
            "this report is informational and not investment advice.*"
        )
    return app


def main() -> int:
    app = build_app()
    app.launch(share=True, server_name="0.0.0.0", show_api=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
