# sg-condo-agent

A reusable Singapore-condo transaction explorer. Pick a project (by short
key like `florence` or any free-form URA project name), pull recent sale
transactions from EdgeProp / URA / SquareFoot / a URA REALIS CSV, classify
each Resale / Sub-Sale as profit / loss / breakeven by FIFO-pairing same-unit
trades, and render either a static HTML report or an interactive Gradio app.

> Originally built for The Florence Residences; generalised into a per-condo
> registry so any project can be added with a few config lines.

## Features

- **Multi-source fetchers** with auto-fallback: EdgeProp → CSV → SquareFoot → URA REALIS.
- **Same-unit pairing** — uses real unit numbers (e.g. `#14-38`) when the
  source provides them; otherwise falls back to a `(block, floor band, area,
  unit type)` heuristic. FIFO matches each Resale / Sub-Sale against the
  earliest unused prior trade in the same physical unit.
- **Two outputs**:
  - `sg-condo-agent` → one-shot static `<condo>.html` report.
  - `sg-condo-share` → interactive Gradio app with KPIs, scatter chart and a
    filterable trade table.
- **Per-condo config registry** in `condos.py` — add a new condo by
  registering its URA project name, EdgeProp asset id, SquareFoot slug, etc.
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
# Registered condo (key from condos.py REGISTRY):
sg-condo-agent --condo florence

# Pin a specific source:
sg-condo-agent --condo florence --source csv --csv ./my_ura_export.csv
sg-condo-agent --condo florence --source edgeprop
sg-condo-agent --condo florence --source ura
sg-condo-agent --condo florence --source squarefoot

# From a Chrome DevTools HAR capture (no cookie file needed):
sg-condo-agent --condo parktown --source har --har ./edgeprop.har

# Ad-hoc by name (URA / CSV sources will work; EdgeProp / SquareFoot need
# slugs registered in condos.py):
sg-condo-agent --condo "Treasure At Tampines" --source ura
```

`--source auto` tries: `har → edgeprop → csv → squarefoot → ura`, skipping
any sources whose inputs aren't supplied (no `--har`, no `edgeprop_asset_id`,
etc.). Output defaults to `<condo-key>.html`; override with `--out`.

### HAR source workflow (no cookies)

EdgeProp blocks unauthenticated automated traffic, so the live `edgeprop`
fetcher needs `EDGEPROP_COOKIE_FILE`. The `har` source side-steps this by
parsing transaction responses directly from a Chrome DevTools capture:

1. Open the project page on edgeprop.sg in Chrome.
2. DevTools → Network → click the project's "View all transactions"
   button, scroll / paginate until **every** row is loaded (each page is one
   `task=tx` XHR).
3. Right-click any row in the network panel → **Save all as HAR with
   content**.
4. `sg-condo-agent --condo <key> --source har --har <path>`.

If the HAR only captured part of the rows, the fetcher prints a coverage
warning so you know to scroll further and re-save.

### Interactive Gradio app

```bash
sg-condo-share --condo florence
sg-condo-share --condo florence --share          # public Gradio link
sg-condo-share --condo "Treasure At Tampines" --source ura
```

### Add a new condo

Edit `src/sg_condo_agent/condos.py` and append a `Condo(...)` entry to
`REGISTRY`. The minimum needed for URA / CSV is `ura_project_name`. To enable
EdgeProp also set `edgeprop_asset_id` (and ideally `edgeprop_slug`); for
SquareFoot set `squarefoot_slug`.

```python
"treasure": Condo(
    key="treasure",
    name="Treasure At Tampines",
    ura_project_name="TREASURE AT TAMPINES",
    location="Tampines Lane",
    district="D18",
    tenure="99-yr from 2018",
    top_year=2023,
    units=2203,
),
```

## Project layout

```
src/sg_condo_agent/
  cli.py            # static HTML CLI entrypoint
  app.py            # Gradio interactive app
  condos.py         # Condo dataclass + REGISTRY
  models.py         # Trade dataclass + pair_key
  pairing.py        # FIFO same-unit profit classifier
  render.py         # HTML report renderer
  template.html     # report template
  fetchers/
    __init__.py     # fetch(condo, source) orchestrator
    edgeprop.py     # EdgeProp scraper (URA-sourced)
    squarefoot.py   # SquareFoot scraper
    ura.py          # URA REALIS API
    csv_source.py   # URA REALIS CSV loader
tests/              # pytest suite
docs/               # design spec & plan
```

## Test

```bash
pytest -v
```

## Caveats

- P/L is **gross**. Net profit is typically ~10–15% lower after stamp duty,
  agent commission, and legal fees (depends on holder type and holding period).
- Trades labelled `no_prior` are usually developer New Sale records with no
  later resale yet — not missing data.
- This report is informational, not investment advice.

## Data sources

- [EdgeProp](https://www.edgeprop.sg/) — primary source (its underlying data
  comes from URA REALIS); needs the project's `asset_id`.
- [URA REALIS](https://www.ura.gov.sg/realis) — official Singapore land
  authority transactions database.
- [SquareFoot](https://www.squarefoot.com.sg/) — fallback HTML source.
