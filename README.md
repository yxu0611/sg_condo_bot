# Florence Residences Transaction Agent

Fetches transaction history for **The Florence Residences** (Hougang Ave 2,
D19, 99-yr from 2018, TOP 2022, 1,410 units), classifies each sale as
profit / loss / breakeven by pairing same-unit historical trades, and emits
either a static HTML report or an interactive Gradio app.

## Features

- **Multi-source fetchers** with auto-fallback: EdgeProp → CSV → SquareFoot → URA REALIS.
- **Same-unit pairing** — uses real unit numbers (e.g. `#14-38`) when the
  source provides them; otherwise falls back to a `(block, floor band, area,
  unit type)` heuristic. FIFO matches each Resale / Sub-Sale against the
  earliest unused prior trade in the same physical unit.
- **Two outputs**:
  - `florence-agent` → one-shot static `florence.html` report.
  - `florence-share` → interactive Gradio app with KPIs, scatter chart,
    filterable trade table, and a sharable public link.
- **Gross P/L** — does *not* deduct BSD / ABSD / SSD / agent / legal fees.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Requires Python 3.11+.

## Usage

### Static HTML report

```bash
florence-agent --source auto --out florence.html
# or pin a specific source:
florence-agent --source csv --csv ./my_ura_export.csv
florence-agent --source edgeprop
florence-agent --source squarefoot
florence-agent --source ura
```

`--source auto` tries: `edgeprop → csv → squarefoot → ura` (csv is skipped
unless `--csv` is given). Open the resulting `florence.html` in any browser.

### Interactive Gradio app

```bash
florence-share
```

Launches on `0.0.0.0` with `share=True` so a public Gradio link is printed.

## Project layout

```
src/florence_agent/
  cli.py            # static HTML CLI entrypoint
  app.py            # Gradio interactive app
  models.py         # Trade dataclass + pair_key
  pairing.py        # FIFO same-unit profit classifier
  render.py         # HTML report renderer
  template.html     # report template
  fetchers/
    edgeprop.py     # EdgeProp scraper (URA-sourced)
    squarefoot.py   # SquareFoot scraper
    ura.py          # URA REALIS API
    csv_source.py   # URA REALIS CSV loader
tests/              # pytest suite for each fetcher + pairing + render
docs/               # design spec & plan
```

## Test

```bash
pytest -v
```

## Caveats

- P/L is **gross**. Net profit is typically ~10–15% lower after stamp duty,
  agent commission, and legal fees (depends on holder type and holding period).
- Trades labeled `no_prior` are usually developer New Sale records with no
  later resale yet — not missing data.
- This report is informational, not investment advice.

## Data sources

- [EdgeProp](https://www.edgeprop.sg/) — primary source (its underlying data
  comes from URA REALIS); project asset_id `291412`.
- [URA REALIS](https://www.ura.gov.sg/realis) — official Singapore land
  authority transactions database.
- [SquareFoot](https://www.squarefoot.com.sg/) — fallback HTML source.
