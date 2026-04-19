# MF Analyser 📊

> A Python toolkit for analysing Indian Mutual Funds — NAV returns, multi-strategy backtesting, and AUM tracking.

---

## Features

| Feature | Description |
|---|---|
| 📈 NAV History | Fetch full NAV history for any AMFI scheme |
| 💵 Returns | Absolute & CAGR for any date range + standard trailing periods (1M to 10Y) |
| 🔄 Rolling Returns | 1Y/3Y/5Y rolling CAGR distribution (min/median/max) |
| 📉 Drawdown | Maximum drawdown + recovery analysis |
| 🤖 Strategies | SIP, Lump Sum, Value Averaging, Momentum (MA crossover), SIP+Stop-Loss |
| 📊 Comparison | Automatic peer discovery and performance ranking within category |
| 📁 Holdings | Portfolio snapshots, stock-level diffs, and sector-wise distribution |
| 🏦 AUM Tracking | Fetch industry-wide AUM rankings and [bold]quarterly growth trends[/bold] (2011-Present) |
| 💾 CSV Cache | Local cache reduces redundant network calls (auto-refreshes after 24h) |
| 🖥️ CLI | Rich terminal output via `mfa` command |
| 📓 Notebooks | Interactive Jupyter notebooks with Plotly charts |

---

## Quickstart

### 1. Install dependencies

```bash
uv sync
```

To also install Jupyter:
```bash
uv sync --extra notebook
```

### 2. Use the CLI

```bash
# List pre-configured default funds
uv run mfa funds

# Search for a fund by name
uv run mfa search "mirae large cap"

# View returns for a fund (all trailing periods)
uv run mfa returns 118825

# Compare a fund with its top 5 category peers
uv run mfa compare 122639 --limit 5

# View portfolio holdings and sector allocation
uv run mfa holdings 122639

# View portfolio changes (requires 2+ cached snapshots)
uv run mfa holdings-diff 122639

# Run a SIP backtest (5000/month from Jan 2019)
uv run mfa strategy sip 118825 --amount 5000 --from-date 2019-01-01

# Run a Lump Sum backtest
uv run mfa strategy lumpsum 118825 --amount 100000 --from-date 2019-01-01

# Value averaging
uv run mfa strategy va 118825 --start-amount 5000 --growth-rate 1.0 --from-date 2020-01-01

# Momentum strategy (MA50 crossover MA200)
uv run mfa strategy momentum 118825 --amount 100000 --fast 50 --slow 200

# SIP with 20% stop-loss
uv run mfa strategy stoploss 118825 --amount 5000 --stop-loss 20

# Fetch Top 10 largest mutual fund schemes in India
uv run mfa aum "Jan-Mar 2024" --top 10

# Fetch Top 20 schemes for a specific partner/AMC
uv run mfa aum "Jan-Mar 2024" --scheme "Mirae"

# Fetch Top 10 largest fund families in India (Combined AUM)
uv run mfa aum "Jan-Mar 2024" --combine --top 10

# Track AUM growth of a fund over the years (2011 to Present)
uv run mfa aum-trend "Parag Parikh Flexi Cap" --start 2013

# Fetch with custom limit and variants combined
uv run mfa aum "Jan-Mar 2024" --scheme "PPFAS" -n 50 --combine

# Cache management
uv run mfa cache list
uv run mfa cache clear 118825
uv run mfa cache clear --all

# Force refresh NAV data
uv run mfa returns 118825 --refresh
```

### 3. Run Jupyter notebooks

```bash
uv run jupyter lab notebooks/
```

Open:
- `01_nav_returns.ipynb` — NAV charts, returns table, rolling CAGR
- `02_strategy_backtest.ipynb` — Compare all strategies side-by-side
- `03_aum_analysis.ipynb` — AUM trend across quarters, sub-scheme breakdown
- `04_peer_comparison.ipynb` — Automatic category discovery and rival analysis
- `05_holdings_analysis.ipynb` — Portfolio concentration and sector allocation

### 4. Run Web Dashboard

```bash
# First, update dependencies with the 'web' extra
uv sync --extra web

# Run the dashboard app locally via the unified CLI
uv run mfa ui
```

---

## Default Funds

| Fund | Code | Category |
|---|---|---|
| Mirae Asset Large Cap Fund | 118825 | Large Cap |
| PPFAS FlexiCap Fund | 122639 | Flexi Cap |
| ICICI Pru Large Cap Fund | 120586 | Large Cap |
| Nippon Multi-Cap Fund | 118650 | Multi Cap |
| Kotak Midcap Fund | 119775 | Mid Cap |
| HDFC Small Cap Fund | 130503 | Small Cap |
| Nippon Small Cap Fund | 118778 | Small Cap |
| UTI Nifty 50 Index Fund | 120716 | Index Fund |
| UTI Nifty Next 50 Index Fund | 143341 | Index Fund |
| ICICI Pru Nifty Bank Index Fund | 149858 | Index Fund |

> **Note**: Scheme codes are for the **Direct Growth** variant. Use `mfa search <name>` to find Regular/IDCW variants.

---

## Project Structure

```
mf-analyser/
├── mf_analyser/
│   ├── config.py          # Paths, cache TTL, default fund universe
│   ├── data/
│   │   ├── fetcher.py     # mftool wrapper
│   │   ├── holdings_fetcher.py # Groww portfolio scraper
│   │   └── cache.py       # JSON/CSV read/write cache
│   ├── analysis/
│   │   ├── returns.py     # Returns calculation
│   │   ├── strategies.py  # Strategy backtesting
│   │   ├── comparison.py  # Peer discovery and ranking
│   │   └── holdings.py    # Portfolio analysis and tracking
│   ├── aum/
│   │   └── tracker.py     # AUM trend analysis
│   └── cli.py             # Typer CLI (mfa command)
├── notebooks/             # Jupyter notebooks
├── data/                  # Local CSV cache (git-ignored)
└── tests/                 # pytest test suite
```

---

## Development

```bash
# Run tests
uv run pytest

# Lint
uv run ruff check .

# Fix linting issues
uv run ruff check . --fix
```

---

## Data Source

All data is fetched from [AMFI India](https://www.amfiindia.com/). 
- **NAV Data**: Fetched via the [`mftool`](https://pypi.org/project/mftool/) package.
- **AUM Data**: Fetched directly from the official AMFI REST API for improved reliability and coverage.
- **Holdings**: Scraped from Groww portfolio mirrors.

---

## Roadmap

- [x] Fund holding changes over time
- [x] AUM rankings and scheme-level tracking (Direct/Regular, Growth/IDCW)
- [x] Peer comparison across funds in same category
- [ ] Web dashboard (Streamlit or Dash)
