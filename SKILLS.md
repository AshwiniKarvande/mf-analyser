# MF Analyser AI Agent Skills 🤖

This file defines the capabilities of the MF Analyser project for AI coding assistants.

## Data Fetching & Caching
- **Search Schemes**: Find AMFI scheme codes by name.
    - `mf_analyser.data.cache.search_cached_schemes(query)`
- **Get NAV**: Fetch historical NAV with local CSV caching.
    - `mf_analyser.data.cache.get_nav(scheme_code, force_refresh=False)`
- **Get AUM**: Fetch Average AUM data for a quarter.
    - `mf_analyser.data.cache.get_aum(quarter, force_refresh=False)`

## Returns Analysis
- **CGR/Absolute Returns**: Calculate returns for a specific period.
    - `mf_analyser.analysis.returns.cagr(df, start_date, end_date)`
- **Rolling Returns**: Generate rolling 1Y/3Y/5Y return series.
    - `mf_analyser.analysis.returns.rolling_returns(df, window_years)`
- **Trailing Returns**: Standard 1M to 10Y returns table.
    - `mf_analyser.analysis.returns.returns_table(df)`

## Investment Backtesting
- **SIP**: Systematic Investment Plan simulation.
    - `mf_analyser.analysis.strategies.sip(df, monthly_amount, ...)`
- **Lump Sum**: One-time investment simulation.
    - `mf_analyser.analysis.strategies.lump_sum(df, amount, ...)`
- **Value Averaging**: Dynamic investment based on target growth.
    - `mf_analyser.analysis.strategies.value_averaging(df, ...)`
- **Momentum**: Moving average crossover strategy.
    - `mf_analyser.analysis.strategies.momentum_ma(df, ...)`
- **SIP + Stop-Loss**: SIP with drawdown-based exit/re-entry.
    - `mf_analyser.analysis.strategies.sip_with_stop_loss(df, ...)`

## AUM Tracking
- **Quarterly Trends**: Build AUM history across multiple quarters.
    - `mf_analyser.aum.tracker.scheme_aum_trend(scheme_name_query)`
- **Sub-scheme Analysis**: Split AUM by Direct/Regular and Growth/IDCW.
    - `mf_analyser.aum.tracker.subscheme_aum_split(df, base_name)`

## CLI Usage
The `mfa` command provides a rich terminal interface for all the above.
Run `uv run mfa --help` for full details.
