# Florence Residence Transaction Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A one-shot Python CLI that fetches Florence Residences (Singapore D19, 99-yr leasehold) transactions, classifies each as profitable / unprofitable / no_prior, and emits a single self-contained `florence.html` report.

**Architecture:** Pipeline of `fetch → pair → render`. Three fetchers (CSV, squarefoot scraper, URA scraper) behind one interface, picked via CLI flag with auto-fallback. Pairing groups same-unit trades by `(block, floor_range, area, unit_type)` and computes gross P/L. Renderer injects a JSON blob into a static HTML template; the page renders the table + Plotly scatter client-side via CDN.

**Tech Stack:** Python 3.11+, `requests`, `beautifulsoup4`, `pytest`, stdlib `csv`/`json`/`string.Template`. Plotly via CDN, no Python plotly dep.

---

## File Structure

```
florence/
  pyproject.toml                       # deps + pytest config
  README.md                            # how to run
  src/florence_agent/
    __init__.py
    models.py                          # Trade dataclass
    fetchers/
      __init__.py                      # dispatcher with fallback chain
      csv_source.py                    # parse URA REALIS export CSV
      squarefoot.py                    # scrape squarefoot.com.sg project page
      ura.py                           # scrape URA public search page
    pairing.py                         # profit/loss pairing logic
    render.py                          # build florence.html
    cli.py                             # argparse entry, wires it all
    template.html                      # static template with Plotly + table JS
  tests/
    __init__.py
    fixtures/
      sample_ura.csv                   # ~30 rows of synthetic Florence trades
      squarefoot_florence.html         # captured page snippet
    test_models.py
    test_csv_source.py
    test_squarefoot.py
    test_pairing.py
    test_render.py
    test_cli_smoke.py
```

The `fetchers/` split is deliberate: each source has its own quirks and can be edited / re-tested in isolation when an upstream layout changes.

---

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`, `README.md`, `.gitignore`
- Create: `src/florence_agent/__init__.py` (empty)
- Create: `tests/__init__.py` (empty)

- [ ] **Step 1: Init git so commits in later steps work**

```bash
cd /Users/xuyan/Desktop/XuYan/code/cc/github/florence
git init -b main
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "florence-agent"
version = "0.1.0"
description = "Florence Residences (SG) transaction explorer"
requires-python = ">=3.11"
dependencies = [
  "requests>=2.31",
  "beautifulsoup4>=4.12",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
florence-agent = "florence_agent.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
```

- [ ] **Step 3: Write `.gitignore`**

```
__pycache__/
*.egg-info/
.venv/
.pytest_cache/
build/
dist/
florence.html
```

- [ ] **Step 4: Write `README.md`**

```markdown
# Florence Residences Transaction Agent

One-shot script. Fetches Florence Residences condo trades, classifies
profit / loss by pairing same-unit historical trades, emits a static
`florence.html` report.

## Install

    python -m venv .venv && source .venv/bin/activate
    pip install -e ".[dev]"

## Run

    florence-agent --source auto --out florence.html
    # or
    florence-agent --source csv --csv ./my_ura_export.csv

`--source auto` tries: squarefoot → ura → csv (if `--csv` given).

Open `florence.html` in any browser.
```

- [ ] **Step 5: Set up venv and install**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```
Expected: install succeeds, `pytest --version` works.

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "scaffold: project layout, deps, README"
```

---

### Task 2: `Trade` dataclass

**Files:**
- Create: `src/florence_agent/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

`tests/test_models.py`:
```python
from datetime import date
from florence_agent.models import Trade

def test_trade_psf_computed():
    t = Trade(
        contract_date=date(2024, 6, 1),
        block="80",
        floor_range="06-10",
        area_sqft=689,
        unit_type="2BR",
        price_sgd=1_350_000,
        tenure="99 yrs",
        sale_type="Resale",
    )
    assert round(t.psf) == 1959

def test_trade_pair_key_groups_same_unit():
    a = Trade(date(2020, 1, 1), "80", "06-10", 689, "2BR", 1_100_000, "99 yrs", "New Sale")
    b = Trade(date(2024, 6, 1), "80", "06-10", 689, "2BR", 1_350_000, "99 yrs", "Resale")
    assert a.pair_key == b.pair_key
```

- [ ] **Step 2: Run, expect failure**

```bash
pytest tests/test_models.py -v
```
Expected: ImportError / ModuleNotFoundError.

- [ ] **Step 3: Implement `models.py`**

```python
from dataclasses import dataclass
from datetime import date

@dataclass(frozen=True)
class Trade:
    contract_date: date
    block: str
    floor_range: str
    area_sqft: int
    unit_type: str
    price_sgd: int
    tenure: str
    sale_type: str

    @property
    def psf(self) -> float:
        return self.price_sgd / self.area_sqft if self.area_sqft else 0.0

    @property
    def pair_key(self) -> tuple:
        return (self.block, self.floor_range, self.area_sqft, self.unit_type)
```

- [ ] **Step 4: Tests pass**

```bash
pytest tests/test_models.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/florence_agent/models.py tests/test_models.py
git commit -m "feat: Trade dataclass with psf and pair_key"
```

---

### Task 3: CSV fetcher (URA REALIS export schema)

**Files:**
- Create: `src/florence_agent/fetchers/__init__.py` (placeholder for now)
- Create: `src/florence_agent/fetchers/csv_source.py`
- Create: `tests/fixtures/sample_ura.csv`
- Test: `tests/test_csv_source.py`

URA REALIS exports private residential trades with these columns (verbatim):
`Project Name, Street Name, Type, Postal District, Market Segment, Tenure, Type of Sale, No. of Units, Price ($), Nett Price ($), Area (Sqft), Type of Area, Floor Level, Unit Price ($psf), Date of Sale, Property Type`.

`Floor Level` looks like `06 to 10` (URA uses words, not dashes). `Date of Sale` looks like `Jun-24`.

- [ ] **Step 1: Create fixture `tests/fixtures/sample_ura.csv`**

```csv
Project Name,Street Name,Type,Postal District,Market Segment,Tenure,Type of Sale,No. of Units,Price ($),Nett Price ($),Area (Sqft),Type of Area,Floor Level,Unit Price ($psf),Date of Sale,Property Type
FLORENCE RESIDENCES,HOUGANG AVENUE 2,Apartment,19,RCR,99 yrs lease commencing from 2018,New Sale,1,"1,100,000",-,689,Strata,06 to 10,1597,Mar-19,Condominium
FLORENCE RESIDENCES,HOUGANG AVENUE 2,Apartment,19,RCR,99 yrs lease commencing from 2018,Resale,1,"1,350,000",-,689,Strata,06 to 10,1959,Jun-24,Condominium
FLORENCE RESIDENCES,HOUGANG AVENUE 2,Apartment,19,RCR,99 yrs lease commencing from 2018,New Sale,1,"1,520,000",-,915,Strata,11 to 15,1661,May-19,Condominium
FLORENCE RESIDENCES,HOUGANG AVENUE 2,Apartment,19,RCR,99 yrs lease commencing from 2018,Resale,1,"1,470,000",-,915,Strata,11 to 15,1606,Aug-23,Condominium
FLORENCE RESIDENCES,HOUGANG AVENUE 2,Apartment,19,RCR,99 yrs lease commencing from 2018,New Sale,1,"2,100,000",-,1184,Strata,16 to 20,1773,Sep-19,Condominium
```

(Block info isn't in URA exports; we treat the whole project as block `-`.)

- [ ] **Step 2: Write the failing tests**

`tests/test_csv_source.py`:
```python
from datetime import date
from pathlib import Path
from florence_agent.fetchers.csv_source import load_csv

FIXTURE = Path(__file__).parent / "fixtures" / "sample_ura.csv"

def test_load_csv_parses_all_rows():
    trades = load_csv(FIXTURE)
    assert len(trades) == 5

def test_load_csv_parses_price_with_commas():
    trades = load_csv(FIXTURE)
    assert trades[0].price_sgd == 1_100_000

def test_load_csv_parses_floor_range():
    trades = load_csv(FIXTURE)
    assert trades[0].floor_range == "06-10"

def test_load_csv_parses_date_mon_yy():
    trades = load_csv(FIXTURE)
    assert trades[0].contract_date == date(2019, 3, 1)
```

- [ ] **Step 3: Run, expect failure**

```bash
pytest tests/test_csv_source.py -v
```

- [ ] **Step 4: Implement `csv_source.py`**

```python
import csv
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from ..models import Trade


def _parse_floor(level: str) -> str:
    # "06 to 10" -> "06-10"; "B1 to B1" -> "B1-B1"
    return level.strip().replace(" to ", "-")


def _parse_date(s: str) -> date:
    # URA prints "Jun-24" meaning June 2024
    return datetime.strptime(s.strip(), "%b-%y").date()


def _parse_price(s: str) -> int:
    return int(s.replace(",", "").replace("$", "").strip())


def _infer_unit_type(area_sqft: int) -> str:
    # URA CSV does not include #bedrooms; use coarse area buckets.
    if area_sqft < 550:
        return "1BR"
    if area_sqft < 800:
        return "2BR"
    if area_sqft < 1100:
        return "3BR"
    return "4BR+"


def load_csv(path: Path | str) -> list[Trade]:
    path = Path(path)
    out: list[Trade] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if "FLORENCE" not in row["Project Name"].upper():
                continue
            area = int(row["Area (Sqft)"].replace(",", ""))
            out.append(
                Trade(
                    contract_date=_parse_date(row["Date of Sale"]),
                    block="-",
                    floor_range=_parse_floor(row["Floor Level"]),
                    area_sqft=area,
                    unit_type=_infer_unit_type(area),
                    price_sgd=_parse_price(row["Price ($)"]),
                    tenure=row["Tenure"].strip(),
                    sale_type=row["Type of Sale"].strip(),
                )
            )
    return out
```

- [ ] **Step 5: Tests pass**

```bash
pytest tests/test_csv_source.py -v
```
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add src/florence_agent/fetchers/ tests/test_csv_source.py tests/fixtures/sample_ura.csv
git commit -m "feat: CSV fetcher for URA REALIS export"
```

---

### Task 4: Pairing & profit/loss logic

**Files:**
- Create: `src/florence_agent/pairing.py`
- Test: `tests/test_pairing.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_pairing.py`:
```python
from datetime import date
from florence_agent.models import Trade
from florence_agent.pairing import classify

def _t(year, area, price, sale_type="Resale"):
    return Trade(
        contract_date=date(year, 6, 1),
        block="-",
        floor_range="06-10",
        area_sqft=area,
        unit_type="2BR",
        price_sgd=price,
        tenure="99 yrs",
        sale_type=sale_type,
    )

def test_no_prior_when_only_one_trade():
    [c] = classify([_t(2019, 689, 1_100_000, "New Sale")])
    assert c.status == "no_prior"
    assert c.gross_profit is None

def test_profitable_pair():
    rows = classify([
        _t(2019, 689, 1_100_000, "New Sale"),
        _t(2024, 689, 1_350_000, "Resale"),
    ])
    rows.sort(key=lambda r: r.trade.contract_date)
    assert rows[0].status == "no_prior"
    assert rows[1].status == "profitable"
    assert rows[1].gross_profit == 250_000
    assert rows[1].holding_years and round(rows[1].holding_years, 1) == 5.0

def test_unprofitable_pair():
    rows = classify([
        _t(2019, 915, 1_520_000, "New Sale"),
        _t(2023, 915, 1_470_000, "Resale"),
    ])
    rows.sort(key=lambda r: r.trade.contract_date)
    assert rows[1].status == "unprofitable"
    assert rows[1].gross_profit == -50_000

def test_separate_units_do_not_pair():
    # Different floor_range -> different pair_key.
    a = _t(2019, 689, 1_100_000, "New Sale")
    b = Trade(
        contract_date=date(2024, 6, 1),
        block="-", floor_range="11-15",
        area_sqft=689, unit_type="2BR",
        price_sgd=1_350_000, tenure="99 yrs", sale_type="Resale",
    )
    rows = classify([a, b])
    assert all(r.status == "no_prior" for r in rows)
```

- [ ] **Step 2: Run, expect failure**

```bash
pytest tests/test_pairing.py -v
```

- [ ] **Step 3: Implement `pairing.py`**

```python
from dataclasses import dataclass
from typing import Optional

from .models import Trade


@dataclass
class Classified:
    trade: Trade
    status: str  # "profitable" | "unprofitable" | "breakeven" | "no_prior"
    buy: Optional[Trade]
    gross_profit: Optional[int]
    holding_years: Optional[float]
    annualized_return: Optional[float]


def classify(trades: list[Trade]) -> list[Classified]:
    out: list[Classified] = []
    buckets: dict[tuple, list[Trade]] = {}
    for t in trades:
        buckets.setdefault(t.pair_key, []).append(t)

    for key, group in buckets.items():
        group.sort(key=lambda t: t.contract_date)
        for i, sell in enumerate(group):
            if i == 0:
                out.append(Classified(sell, "no_prior", None, None, None, None))
                continue
            buy = group[i - 1]
            profit = sell.price_sgd - buy.price_sgd
            years = (sell.contract_date - buy.contract_date).days / 365.25
            ann = (sell.price_sgd / buy.price_sgd) ** (1 / years) - 1 if years > 0 else None
            if profit > 0:
                status = "profitable"
            elif profit < 0:
                status = "unprofitable"
            else:
                status = "breakeven"
            out.append(Classified(sell, status, buy, profit, years, ann))
    return out
```

- [ ] **Step 4: Tests pass**

```bash
pytest tests/test_pairing.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/florence_agent/pairing.py tests/test_pairing.py
git commit -m "feat: pair same-unit trades and classify profit/loss"
```

---

### Task 5: HTML template + renderer

**Files:**
- Create: `src/florence_agent/template.html`
- Create: `src/florence_agent/render.py`
- Test: `tests/test_render.py`

The template uses `string.Template` placeholders. Trade data is injected as JSON; the table and chart are built client-side.

- [ ] **Step 1: Write the failing tests**

`tests/test_render.py`:
```python
import json
import re
from datetime import date
from florence_agent.models import Trade
from florence_agent.pairing import classify
from florence_agent.render import render_html


def _seed():
    return [
        Trade(date(2019, 3, 1), "-", "06-10", 689, "2BR", 1_100_000, "99 yrs", "New Sale"),
        Trade(date(2024, 6, 1), "-", "06-10", 689, "2BR", 1_350_000, "99 yrs", "Resale"),
    ]


def test_render_returns_html_with_doctype():
    html = render_html(classify(_seed()), source="csv")
    assert html.lstrip().lower().startswith("<!doctype html>")


def test_render_embeds_trade_json():
    html = render_html(classify(_seed()), source="csv")
    m = re.search(r'id="trades-data"[^>]*>(.+?)</script>', html, re.S)
    assert m, "trades-data script not found"
    payload = json.loads(m.group(1))
    assert len(payload) == 2
    assert any(row["status"] == "profitable" for row in payload)


def test_render_includes_summary_counts():
    html = render_html(classify(_seed()), source="csv")
    assert "Total trades" in html
    assert ">2<" in html  # total
```

- [ ] **Step 2: Create the HTML template**

`src/florence_agent/template.html`:
```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Florence Residences — Transactions</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
  body { font-family: -apple-system, system-ui, sans-serif; margin: 24px; color: #1a1a1a; background: #fafafa; }
  h1 { margin: 0 0 4px; font-size: 20px; }
  .meta { color: #666; font-size: 12px; margin-bottom: 20px; }
  .cards { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 24px; }
  .card { background: white; border: 1px solid #e3e3e3; border-radius: 8px; padding: 12px 16px; min-width: 140px; }
  .card .label { font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: .04em; }
  .card .value { font-size: 18px; font-weight: 600; margin-top: 4px; font-variant-numeric: tabular-nums; }
  table { width: 100%; border-collapse: collapse; background: white; font-size: 13px; }
  th, td { padding: 6px 10px; text-align: right; border-bottom: 1px solid #eee; font-variant-numeric: tabular-nums; }
  th:first-child, td:first-child, th.left, td.left { text-align: left; }
  th { background: #f0f0f0; cursor: pointer; user-select: none; position: sticky; top: 0; }
  th:hover { background: #e6e6e6; }
  .tag { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
  .tag-profitable { background: #d6f5dc; color: #0a7d2e; }
  .tag-unprofitable { background: #fbd7d7; color: #b02828; }
  .tag-breakeven { background: #ececec; color: #555; }
  .tag-no_prior { background: #ececec; color: #888; }
  #chart { background: white; border: 1px solid #e3e3e3; border-radius: 8px; padding: 12px; margin-bottom: 24px; }
  .footnote { font-size: 11px; color: #888; margin-top: 16px; }
</style>
</head>
<body>
<h1>Florence Residences — Transaction Report</h1>
<div class="meta">Source: <b>$source</b> · Generated $generated · $count trades · gross P/L excludes stamp duty &amp; fees</div>

<div class="cards">
  <div class="card"><div class="label">Total trades</div><div class="value">$count</div></div>
  <div class="card"><div class="label">Profitable</div><div class="value" style="color:#0a7d2e">$profitable</div></div>
  <div class="card"><div class="label">Unprofitable</div><div class="value" style="color:#b02828">$unprofitable</div></div>
  <div class="card"><div class="label">No prior match</div><div class="value">$no_prior</div></div>
  <div class="card"><div class="label">Total gross P/L</div><div class="value">S$$total_pl</div></div>
  <div class="card"><div class="label">Median PSF</div><div class="value">S$$median_psf</div></div>
</div>

<div id="chart"></div>

<table id="tbl">
  <thead><tr>
    <th class="left" data-key="contract_date">Date</th>
    <th class="left" data-key="floor_range">Floor</th>
    <th data-key="area_sqft">Area (sqft)</th>
    <th data-key="psf">PSF</th>
    <th data-key="price_sgd">Price (S$)</th>
    <th data-key="holding_years">Holding (yrs)</th>
    <th data-key="gross_profit">Gross P/L</th>
    <th data-key="annualized_return">Ann. return</th>
    <th class="left" data-key="status">Status</th>
  </tr></thead>
  <tbody></tbody>
</table>

<div class="footnote">"Same unit" inferred by (block, floor band, area, unit type). URA does not publish unit numbers, so pairings are best-effort. P/L is gross.</div>

<script id="trades-data" type="application/json">$payload</script>
<script>
const rows = JSON.parse(document.getElementById('trades-data').textContent);
const fmt = n => n == null ? '—' : n.toLocaleString('en-SG', {maximumFractionDigits: 0});
const fmtPct = n => n == null ? '—' : (n*100).toFixed(1) + '%';
const fmt1 = n => n == null ? '—' : n.toFixed(1);

function render(data) {
  const tb = document.querySelector('#tbl tbody');
  tb.innerHTML = '';
  for (const r of data) {
    const pl = r.gross_profit;
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="left">${r.contract_date}</td>
      <td class="left">${r.floor_range}</td>
      <td>${fmt(r.area_sqft)}</td>
      <td>${fmt(r.psf)}</td>
      <td>${fmt(r.price_sgd)}</td>
      <td>${fmt1(r.holding_years)}</td>
      <td style="color:${pl == null ? '#888' : pl > 0 ? '#0a7d2e' : pl < 0 ? '#b02828' : '#555'}">${pl == null ? '—' : (pl > 0 ? '+' : '') + fmt(pl)}</td>
      <td>${fmtPct(r.annualized_return)}</td>
      <td class="left"><span class="tag tag-${r.status}">${r.status}</span></td>`;
    tb.appendChild(tr);
  }
}
render([...rows].sort((a,b) => a.contract_date < b.contract_date ? 1 : -1));

// Sortable headers
let lastKey = 'contract_date', asc = false;
document.querySelectorAll('#tbl th').forEach(th => {
  th.addEventListener('click', () => {
    const k = th.dataset.key;
    asc = (k === lastKey) ? !asc : true;
    lastKey = k;
    const sorted = [...rows].sort((a,b) => {
      const va = a[k], vb = b[k];
      if (va == null) return 1;
      if (vb == null) return -1;
      return asc ? (va > vb ? 1 : -1) : (va < vb ? 1 : -1);
    });
    render(sorted);
  });
});

// Plotly scatter
const colorOf = s => ({profitable:'#0a7d2e', unprofitable:'#b02828', breakeven:'#888', no_prior:'#bbb'})[s];
Plotly.newPlot('chart', [{
  x: rows.map(r => r.contract_date),
  y: rows.map(r => r.psf),
  mode: 'markers',
  marker: { color: rows.map(r => colorOf(r.status)), size: 9, line: {width: 0.5, color: '#333'} },
  text: rows.map(r => `${r.floor_range} · ${r.area_sqft} sqft · S$${fmt(r.price_sgd)} · ${r.status}`),
  hovertemplate: '%{x}<br>S$%{y:,.0f} psf<br>%{text}<extra></extra>',
}], {
  margin: {t: 8, r: 8, b: 40, l: 56},
  xaxis: {title: 'Contract date'},
  yaxis: {title: 'S$ / sqft'},
  height: 360,
}, {displayModeBar: false, responsive: true});
</script>
</body>
</html>
```

- [ ] **Step 3: Implement `render.py`**

```python
import json
from datetime import datetime
from importlib.resources import files
from statistics import median
from string import Template

from .pairing import Classified


def _row_dict(c: Classified) -> dict:
    t = c.trade
    return {
        "contract_date": t.contract_date.isoformat(),
        "block": t.block,
        "floor_range": t.floor_range,
        "area_sqft": t.area_sqft,
        "unit_type": t.unit_type,
        "price_sgd": t.price_sgd,
        "psf": round(t.psf, 1),
        "tenure": t.tenure,
        "sale_type": t.sale_type,
        "status": c.status,
        "gross_profit": c.gross_profit,
        "holding_years": round(c.holding_years, 2) if c.holding_years else None,
        "annualized_return": round(c.annualized_return, 4) if c.annualized_return else None,
    }


def render_html(classified: list[Classified], *, source: str) -> str:
    rows = [_row_dict(c) for c in classified]
    pls = [r["gross_profit"] for r in rows if r["gross_profit"] is not None]
    psfs = [r["psf"] for r in rows]

    counts = {"profitable": 0, "unprofitable": 0, "breakeven": 0, "no_prior": 0}
    for r in rows:
        counts[r["status"]] += 1

    tpl = Template((files("florence_agent") / "template.html").read_text(encoding="utf-8"))
    return tpl.safe_substitute(
        source=source,
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        count=len(rows),
        profitable=counts["profitable"],
        unprofitable=counts["unprofitable"],
        no_prior=counts["no_prior"],
        total_pl=f"{sum(pls):,}" if pls else "0",
        median_psf=f"{median(psfs):,.0f}" if psfs else "—",
        payload=json.dumps(rows),
    )
```

- [ ] **Step 4: Make template a package data file**

Add to `pyproject.toml` under `[tool.setuptools]`:

```toml
[tool.setuptools.package-data]
florence_agent = ["template.html"]
```

Reinstall so the data file is registered:

```bash
pip install -e ".[dev]"
```

- [ ] **Step 5: Tests pass**

```bash
pytest tests/test_render.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add src/florence_agent/template.html src/florence_agent/render.py tests/test_render.py pyproject.toml
git commit -m "feat: HTML renderer with summary cards, sortable table, Plotly scatter"
```

---

### Task 6: squarefoot.com.sg fetcher

squarefoot publishes Florence Residences trades on its project page. The HTML structure (verified pattern, may drift): a `<table>` with class `transaction-table` whose rows carry `data-` attributes for date/floor/area/price.

**Files:**
- Create: `src/florence_agent/fetchers/squarefoot.py`
- Create: `tests/fixtures/squarefoot_florence.html`
- Test: `tests/test_squarefoot.py`

- [ ] **Step 1: Create the fixture**

`tests/fixtures/squarefoot_florence.html`:
```html
<!doctype html><html><body>
<table class="transaction-table">
  <thead><tr><th>Date</th><th>Block</th><th>Unit</th><th>Area</th><th>Price</th><th>Type</th></tr></thead>
  <tbody>
    <tr>
      <td>Jun 2024</td><td>80</td><td>#06-XX</td>
      <td>689 sqft</td><td>S$1,350,000</td><td>Resale</td>
    </tr>
    <tr>
      <td>Mar 2019</td><td>80</td><td>#06-XX</td>
      <td>689 sqft</td><td>S$1,100,000</td><td>New Sale</td>
    </tr>
    <tr>
      <td>Aug 2023</td><td>82</td><td>#11-XX</td>
      <td>915 sqft</td><td>S$1,470,000</td><td>Resale</td>
    </tr>
  </tbody>
</table>
</body></html>
```

- [ ] **Step 2: Write the failing tests**

`tests/test_squarefoot.py`:
```python
from datetime import date
from pathlib import Path
from florence_agent.fetchers.squarefoot import parse_squarefoot_html

FIXTURE = Path(__file__).parent / "fixtures" / "squarefoot_florence.html"

def test_parse_returns_all_rows():
    trades = parse_squarefoot_html(FIXTURE.read_text())
    assert len(trades) == 3

def test_parse_extracts_block_and_floor():
    trades = parse_squarefoot_html(FIXTURE.read_text())
    t = next(t for t in trades if t.area_sqft == 689 and t.contract_date == date(2024, 6, 1))
    assert t.block == "80"
    assert t.floor_range == "06-10"  # #06-XX -> 06-10 bucket

def test_parse_handles_price_and_area():
    trades = parse_squarefoot_html(FIXTURE.read_text())
    t = next(t for t in trades if t.contract_date == date(2019, 3, 1))
    assert t.price_sgd == 1_100_000
    assert t.area_sqft == 689
```

- [ ] **Step 3: Run, expect failure**

```bash
pytest tests/test_squarefoot.py -v
```

- [ ] **Step 4: Implement `squarefoot.py`**

```python
import re
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

from ..models import Trade
from .csv_source import _infer_unit_type

PROJECT_URL = "https://www.squarefoot.com.sg/private-property/florence-residences-singapore"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
    "Accept-Language": "en-SG,en;q=0.9",
}


def _floor_to_band(unit_label: str) -> str:
    # "#06-XX" -> floor 6 -> band "06-10"
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


def fetch_squarefoot() -> list[Trade]:
    r = requests.get(PROJECT_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return parse_squarefoot_html(r.text)
```

- [ ] **Step 5: Tests pass**

```bash
pytest tests/test_squarefoot.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add src/florence_agent/fetchers/squarefoot.py tests/test_squarefoot.py tests/fixtures/squarefoot_florence.html
git commit -m "feat: squarefoot fetcher with HTML parse + tests"
```

---

### Task 7: URA public-page fetcher

URA's public site exposes JSON via `https://www.ura.gov.sg/realEstateIIWeb/transaction/searchByProject.action` with a project name parameter. Response shape varies; this task wraps the call defensively and tolerates schema drift.

**Files:**
- Create: `src/florence_agent/fetchers/ura.py`
- Test: covered indirectly by smoke test in Task 8 + a unit test for the JSON parser

- [ ] **Step 1: Implement `ura.py` with a parser separable from the network call**

```python
import re
from datetime import date, datetime

import requests

from ..models import Trade
from .csv_source import _infer_unit_type

ENDPOINT = "https://www.ura.gov.sg/realEstateIIWeb/transaction/searchByProject.action"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
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


def parse_ura_json(payload: dict) -> list[Trade]:
    """Defensive: walk known and likely keys for the transaction list."""
    rows = (
        payload.get("transactionList")
        or payload.get("transactions")
        or payload.get("result", {}).get("transactionList")
        or []
    )
    out: list[Trade] = []
    for r in rows:
        if "FLORENCE" not in str(r.get("projectName", "")).upper():
            continue
        area = int(re.sub(r"[^\d]", "", str(r.get("area") or r.get("areaSqft") or "0")) or 0)
        if not area:
            continue
        price = int(re.sub(r"[^\d]", "", str(r.get("price") or r.get("transactedPrice") or "0")) or 0)
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


def fetch_ura() -> list[Trade]:
    r = requests.get(
        ENDPOINT,
        params={"projectName": "FLORENCE RESIDENCES"},
        headers=HEADERS,
        timeout=20,
    )
    r.raise_for_status()
    return parse_ura_json(r.json())
```

- [ ] **Step 2: Add a parser unit test**

`tests/test_ura.py`:
```python
from florence_agent.fetchers.ura import parse_ura_json

PAYLOAD = {
    "transactionList": [
        {
            "projectName": "FLORENCE RESIDENCES",
            "block": "80",
            "floorLevel": "06 to 10",
            "area": "689",
            "price": "1350000",
            "contractDate": "Jun-24",
            "tenure": "99 yrs lease commencing from 2018",
            "typeOfSale": "Resale",
        },
        {"projectName": "Other Condo", "area": "1000", "price": "2000000"},
    ]
}


def test_parse_filters_to_florence():
    trades = parse_ura_json(PAYLOAD)
    assert len(trades) == 1
    assert trades[0].block == "80"
    assert trades[0].price_sgd == 1_350_000
    assert trades[0].floor_range == "06-10"
```

- [ ] **Step 3: Tests pass**

```bash
pytest tests/test_ura.py -v
```
Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add src/florence_agent/fetchers/ura.py tests/test_ura.py
git commit -m "feat: URA fetcher with defensive JSON parser"
```

---

### Task 8: Fetcher dispatcher + CLI + end-to-end smoke

**Files:**
- Modify: `src/florence_agent/fetchers/__init__.py`
- Create: `src/florence_agent/cli.py`
- Test: `tests/test_cli_smoke.py`

- [ ] **Step 1: Write the dispatcher**

`src/florence_agent/fetchers/__init__.py`:
```python
from pathlib import Path
from typing import Optional

from ..models import Trade


def fetch(source: str, csv_path: Optional[Path] = None) -> tuple[list[Trade], str]:
    """Returns (trades, source_used). 'auto' tries squarefoot, ura, csv in order."""
    order = {
        "auto": ["squarefoot", "ura", "csv"],
        "squarefoot": ["squarefoot"],
        "ura": ["ura"],
        "csv": ["csv"],
    }[source]

    last_err: Optional[Exception] = None
    for src in order:
        try:
            if src == "csv":
                if csv_path is None:
                    continue
                from .csv_source import load_csv
                trades = load_csv(csv_path)
            elif src == "squarefoot":
                from .squarefoot import fetch_squarefoot
                trades = fetch_squarefoot()
            elif src == "ura":
                from .ura import fetch_ura
                trades = fetch_ura()
            else:
                continue
            if trades:
                return trades, src
        except Exception as e:  # network, parse, anything
            last_err = e
            continue

    if last_err and source != "auto":
        raise last_err
    return [], "none"
```

- [ ] **Step 2: Write the CLI**

`src/florence_agent/cli.py`:
```python
import argparse
import sys
from pathlib import Path

from .fetchers import fetch
from .pairing import classify
from .render import render_html


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="florence-agent")
    p.add_argument("--source", choices=["auto", "squarefoot", "ura", "csv"], default="auto")
    p.add_argument("--csv", type=Path, help="Path to URA REALIS CSV export")
    p.add_argument("--out", type=Path, default=Path("florence.html"))
    args = p.parse_args(argv)

    trades, used = fetch(args.source, args.csv)
    if not trades:
        print(f"no trades found from source={args.source}", file=sys.stderr)
        return 2

    print(f"fetched {len(trades)} trades from {used}")
    classified = classify(trades)
    args.out.write_text(render_html(classified, source=used), encoding="utf-8")
    print(f"wrote {args.out} ({args.out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Write the end-to-end smoke test**

`tests/test_cli_smoke.py`:
```python
from pathlib import Path
from florence_agent.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "sample_ura.csv"


def test_cli_csv_produces_html(tmp_path):
    out = tmp_path / "florence.html"
    rc = main(["--source", "csv", "--csv", str(FIXTURE), "--out", str(out)])
    assert rc == 0
    html = out.read_text()
    assert "<!doctype html>" in html.lower()
    assert "Florence Residences" in html
    assert "trades-data" in html
    assert out.stat().st_size > 5_000  # has actual content
```

- [ ] **Step 4: Run all tests**

```bash
pytest -v
```
Expected: every test in the suite passes.

- [ ] **Step 5: Real run with fixture**

```bash
florence-agent --source csv --csv tests/fixtures/sample_ura.csv --out florence.html
```
Expected: stdout shows `fetched 5 trades from csv` and `wrote florence.html (...)`. Open `florence.html`: 5 rows, scatter has 5 dots.

- [ ] **Step 6: Real run with auto (will hit the network)**

```bash
florence-agent --source auto --csv tests/fixtures/sample_ura.csv --out florence.html
```
Expected: either pulls from squarefoot/ura (>50 trades) or falls back to csv. stdout names the source actually used.

If both web sources fail, the squarefoot or URA selectors likely need updating against the live page — this is the expected place where a small adjustment is needed; the parser unit tests still cover the structure they expect.

- [ ] **Step 7: Commit**

```bash
git add src/florence_agent/fetchers/__init__.py src/florence_agent/cli.py tests/test_cli_smoke.py
git commit -m "feat: fetcher dispatcher, CLI, end-to-end smoke test"
```

---

## Self-review notes

- Spec coverage: data sources (Tasks 3/6/7/8), pairing (Task 4), HTML output incl. summary/table/scatter (Task 5), CLI + auto-fallback + source logging (Task 8). ✓
- Type consistency: `Trade` defined Task 2, used by all fetchers; `Classified` defined Task 4, consumed by `render_html` Task 5; `_infer_unit_type` defined in `csv_source` and reused by `squarefoot` and `ura` (single source of truth). ✓
- Known fragility: live HTML/JSON selectors in Tasks 6 and 7 may drift; both have fixture-based unit tests so adjustments are localized.
