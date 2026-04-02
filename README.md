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
| 🏦 AUM Tracking | Quarter-over-quarter AUM trends, sub-scheme split (Direct/Regular, Growth/IDCW) |
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
uv run mfa returns 118989

# View returns with custom date range, rolling summary, and drawdown
uv run mfa returns 118989 --from-date 2019-01-01 --rolling --drawdown

# Run a SIP backtest (5000/month from Jan 2019)
uv run mfa strategy sip 118989 --amount 5000 --from-date 2019-01-01

# Run a Lump Sum backtest
uv run mfa strategy lumpsum 118989 --amount 100000 --from-date 2019-01-01

# Value averaging
uv run mfa strategy va 118989 --start-amount 5000 --growth-rate 1.0 --from-date 2020-01-01

# Momentum strategy (MA50 crossover MA200)
uv run mfa strategy momentum 118989 --amount 100000 --fast 50 --slow 200

# SIP with 20% stop-loss
uv run mfa strategy stoploss 118989 --amount 5000 --stop-loss 20

# Fetch AUM for a quarter
uv run mfa aum "Jan-Mar 2024" --scheme "Mirae"

# Cache management
uv run mfa cache list
uv run mfa cache clear 118989
uv run mfa cache clear --all

# Force refresh NAV data
uv run mfa returns 118989 --refresh
```

### 3. Run Jupyter notebooks

```bash
uv run jupyter lab notebooks/
```

Open:
- `01_nav_returns.ipynb` — NAV charts, returns table, rolling CAGR
- `02_strategy_backtest.ipynb` — Compare all strategies side-by-side
- `03_aum_analysis.ipynb` — AUM trend across quarters, sub-scheme breakdown

---

## Default Funds

| Fund | Code | Category |
|---|---|---|
| Mirae Asset Large Cap Fund | 118989 | Large Cap |
| PPFAS FlexiCap Fund | 122639 | Flexi Cap |
| ICICI Pru Large Cap Fund | 120586 | Large Cap |
| Nippon Multi-Cap Fund | 118825 | Multi Cap |
| Kotak Midcap Fund | 120465 | Mid Cap |
| HDFC Small Cap Fund | 118731 | Small Cap |
| Nippon Small Cap Fund | 118778 | Small Cap |
| UTI Nifty 50 Index Fund | 120716 | Index Fund |
| UTI Nifty Next 50 Index Fund | 120684 | Index Fund |
| ICICI Pru Nifty Bank Index Fund | 120620 | Index Fund |

> **Note**: Scheme codes are for the **Direct Growth** variant. Use `mfa search <name>` to find Regular/IDCW variants.

---

## Project Structure

```
mf-analyser/
├── mf_analyser/
│   ├── config.py          # Paths, cache TTL, default fund universe
│   ├── data/
│   │   ├── fetcher.py     # mftool wrapper
│   │   └── cache.py       # CSV read/write cache
│   ├── analysis/
│   │   ├── returns.py     # Returns calculation
│   │   └── strategies.py  # Strategy backtesting
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

All data is fetched from [AMFI India](https://www.amfiindia.com/) via the [`mftool`](https://pypi.org/project/mftool/) package. Accuracy depends on AMFI data availability.

---

## Roadmap

- [ ] Fund holding changes over time
- [ ] AUM changes at sub-scheme level (Direct/Regular, Growth/IDCW)
- [ ] Peer comparison across funds in same category
- [ ] Web dashboard (Streamlit or Dash)
