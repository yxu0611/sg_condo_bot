# Florence Residence Transaction Agent — Design

## Goal

A one-shot Python script that fetches recent transactions of the Singapore
condo "Florence Residences" (Hougang, D19, 99-yr leasehold), classifies each
trade as profitable / unprofitable / no_prior, and renders a single static
`florence.html` report.

## Data acquisition

No URA API key available. Try sources in order, log which one was used:

1. **URA public transaction search** (`ura.gov.sg/realEstateIIWeb/transaction/search.action`)
   — public AJAX backend, no key needed. Authoritative.
2. **squarefoot.com.sg** Florence Residences project page — fallback if URA
   blocks. Same underlying URA REALIS data, easier HTML.
3. **Local CSV** — `--csv path` flag accepts a manual URA REALIS export.

Each transaction row carries: contract date, project name, address/block,
floor range (e.g. `06-10`), area (sqft), price (S$), unit type (#bed),
tenure, type of sale.

## Profit / loss inference

URA does not publish unit numbers, only floor ranges. Pair likely-same-unit
trades by composite key:

```
key = (block, floor_range, area_sqft, unit_type)
```

Within a key bucket, sort by contract date and pair adjacent trades:

- earlier = buy, later = sell
- `gross_profit = sell_price - buy_price`
- `holding_years = (sell_date - buy_date).days / 365.25`
- annualized return = `(sell/buy)^(1/years) - 1`
- status: `profitable` if gross_profit > 0, `unprofitable` if < 0, else
  `breakeven`. Trades with no earlier match → `no_prior`.

Excludes stamp duty / agent fees — explicitly labelled "gross" in HTML.

## HTML output

Single self-contained file `florence.html`:

- **Header**: project metadata, last-updated timestamp, data source used.
- **Summary cards**: total trades, count by status, total gross P/L, median
  holding period, median PSF.
- **Transactions table**: sortable columns (date, block, floor, area, PSF,
  price, holding, P/L, status with color tag).
- **Scatter chart**: x = contract date, y = PSF, color = status. Hover
  tooltip with full row. Plotly via CDN (works offline once cached).

Styling: light theme, monospace numerics, status color coding —
`profitable` green, `unprofitable` red, `no_prior` gray.

## Script structure

```
florence_agent.py
  fetch_transactions(source) -> list[Trade]
  pair_transactions(trades)  -> list[Trade]   # adds profit fields
  render_html(trades, meta)  -> writes florence.html
  main()                     # CLI: --source ura|squarefoot|csv --csv PATH --out PATH
```

Deps: `requests`, `beautifulsoup4`, `pandas`. Plotly via CDN, no python
plotly package.

## Out of scope (YAGNI)

- No daemon / scheduling / database
- No auth, no web service
- No tax / fee modelling
- No multi-project support — Florence Residences only

## Success criteria

1. Running `python florence_agent.py` produces `florence.html` populated
   with > 50 historical Florence Residences trades.
2. At least one trade in each status category appears in the report.
3. The data source used is logged to stdout.
4. Opening `florence.html` in a browser shows summary cards, sortable
   table, and an interactive scatter chart.
