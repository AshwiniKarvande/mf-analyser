# MF Analyser — AI Agent Context 🧠

## Architecture Overview
The project follows a modular functional approach:
1. **Config**: `config.py` holds paths and the `DEFAULT_FUNDS` universe.
2. **Data Layer**:
    - `fetcher.py`: Thin wrapper around `mftool`.
    - `cache.py`: Manages CSV files in `data/nav/` and `data/aum/`. This is the primary entry point for data.
3. **Analysis Layer**:
    - `returns.py`: Stateless calculations on DataFrames (date, nav).
    - `strategies.py`: Implements backtesting logic. Each strategy returns a `StrategyResult` object.
4. **AUM Layer**: Handles quarterly AUM data processing.
5. **CLI**: `cli.py` uses `Typer` to expose functions to the terminal.

## Data Contracts
- **NAV DataFrames**: Always contain `date` (datetime64) and `nav` (float64).
- **AUM DataFrames**: Contain `amc`, `scheme_name`, `scheme_code`, `aum_cr`.

## Key Patterns
- Use `mf_analyser.data.cache.get_nav` instead of `fetcher.py` to leverage local caching.
- All dates in function arguments should support `date` objects or `ISO strings`.
- Strategies return a `summary()` dict for easy printing/logging.

## Directory Map
- `mf_analyser/`: Source code.
- `data/`: Local storage for cached CSVs (git-ignored).
- `notebooks/`: Jupyter analysis samples.
- `tests/`: Extensive pytest suite.

## Maintenance Instructions
Whenever you make project changes (such as adding new features, modifying APIs, or refactoring), you **must** ensure the following are kept up-to-date:
- `README.md`
- `SKILLS.md`
- Jupyter notebooks in the `notebooks/` directory
- Test cases in the `tests/` directory
