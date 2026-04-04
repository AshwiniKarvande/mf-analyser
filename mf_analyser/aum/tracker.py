"""
tracker.py — AUM (Assets Under Management) trend analysis.

Tracks AUM across multiple quarters and optionally filters by:
  - AMC (fund house)
  - Scheme name substring (to capture sub-schemes: Direct/Regular, Growth/IDCW)
  - Category
"""

from __future__ import annotations

import logging

import pandas as pd

from mf_analyser.data.cache import get_aum

logger = logging.getLogger(__name__)


# ─── Standard quarters helper ─────────────────────────────────────────────────

def generate_quarters(start_year: int = 2011, end_year: int | None = None) -> list[str]:
    """
    Generate a list of quarter strings from start_year to end_year (inclusive).

    Format: "Jan-Mar 2020", "Apr-Jun 2020", "Jul-Sep 2020", "Oct-Dec 2020"
    """
    import datetime
    today = datetime.date.today()
    if end_year is None:
        end_year = today.year

    # Mapping of start month of quarter to label
    # 1: Jan-Mar, 4: Apr-Jun, 7: Jul-Sep, 10: Oct-Dec
    labels = {1: "Jan-Mar", 4: "Apr-Jun", 7: "Jul-Sep", 10: "Oct-Dec"}
    quarters = []
    
    for year in range(start_year, end_year + 1):
        for start_month, label in labels.items():
            # A quarter is only fully available AFTER it ends.
            # E.g. Jan-Mar (1-3) is available in April (4).
            end_month = start_month + 2
            if year < today.year or (year == today.year and today.month > end_month):
                quarters.append(f"{label} {year}")
    return quarters


# ─── Multi-quarter fetch & build time series ──────────────────────────────────

def build_aum_timeseries(
    quarters: list[str],
    scheme_filter: str | None = None,
    amc_filter: str | None = None,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Fetch AUM for a list of quarters and concatenate into one DataFrame.

    Args:
        quarters:       List of quarter strings (e.g. from generate_quarters())
        scheme_filter:  Optional substring to filter scheme names (case-insensitive)
        amc_filter:     Optional AMC name substring filter (case-insensitive)
        force_refresh:  Bypass cache

    Returns:
        DataFrame with columns: quarter, amc (if present), scheme_name, scheme_code, aum_cr, ...
        Sorted by quarter chronologically.
    """
    frames: list[pd.DataFrame] = []

    for q in quarters:
        try:
            df = get_aum(q, force_refresh=force_refresh)
        except Exception as exc:
            logger.warning("Could not fetch AUM for quarter %s: %s", q, exc)
            continue

        if scheme_filter:
            col = _find_col(df, "scheme")
            if col:
                df = df[df[col].str.contains(scheme_filter, case=False, na=False)]

        if amc_filter:
            col = _find_col(df, "amc")
            if col:
                df = df[df[col].str.contains(amc_filter, case=False, na=False)]

        frames.append(df)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    combined = _sort_by_quarter(combined)
    return combined


def _find_col(df: pd.DataFrame, keyword: str) -> str | None:
    """Return first column name containing the keyword."""
    matches = [c for c in df.columns if keyword.lower() in c.lower()]
    return matches[0] if matches else None


# ─── Quarter sorting ──────────────────────────────────────────────────────────

_QUARTER_ORDER = {"Jan-Mar": 1, "Apr-Jun": 2, "Jul-Sep": 3, "Oct-Dec": 4}


def _quarter_sort_key(q: str) -> tuple[int, int]:
    parts = q.split()
    if len(parts) != 2:
        return (9999, 0)
    label, year_str = parts
    return (int(year_str), _QUARTER_ORDER.get(label, 0))


def _sort_by_quarter(df: pd.DataFrame) -> pd.DataFrame:
    if "quarter" not in df.columns:
        return df
    df = df.copy()
    df["_sort_key"] = df["quarter"].map(_quarter_sort_key)
    df = df.sort_values("_sort_key").drop(columns=["_sort_key"]).reset_index(drop=True)
    return df


# ─── AUM trend for a specific scheme ─────────────────────────────────────────

def scheme_aum_trend(
    scheme_name_query: str,
    start_year: int = 2011,
    end_year: int | None = None,
    combine: bool = True,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Build AUM time series for a specific fund family (combined) or scheme.

    Args:
        scheme_name_query:  Fund name substring (e.g. "Parag Parikh Flexi")
        start_year:         Starting year for trend
        end_year:           End year for trend
        combine:            If True, groups all variants (Direct/Regular) into one figure.
        force_refresh:      Bypass cache

    Returns:
        DataFrame with columns: quarter, scheme_name, aum_cr
        One row per quarter where data is available.
    """
    from mf_analyser.cli import _normalize_fund_name

    # Fetch one extra year before start_year to provide a growth baseline
    # for the first displayed quarter (if cache allows).
    fetch_start = max(2011, start_year - 1)
    quarters = generate_quarters(fetch_start, end_year)
    ts = build_aum_timeseries(
        quarters,
        scheme_filter=scheme_name_query,
        force_refresh=force_refresh,
    )
    
    # We store the intended display start_year in the dataframe metadata
    # or just rely on the CLI filtering it. The caller will filter.

    if ts.empty:
        return ts

    if combine:
        # Group by quarter and normalized fund family name
        ts["fund_family"] = ts["scheme_name"].apply(_normalize_fund_name)
        # We also group by AMC to ensure we don't merge identical names across different AMCs
        ts = ts.groupby(["quarter", "amc", "fund_family"])["aum_cr"].sum().reset_index()
        # Pick the normalized name for display
        ts.rename(columns={"fund_family": "scheme_name"}, inplace=True)
    else:
        # If not combining, keep individual scheme name AND code
        ts = ts.groupby(["quarter", "amc", "scheme_name", "scheme_code"])["aum_cr"].sum().reset_index()

    ts = _sort_by_quarter(ts)
    return ts


# ─── AUM growth metrics ───────────────────────────────────────────────────────

def aum_growth_summary(aum_ts: pd.DataFrame, aum_col: str = "aum_cr") -> pd.DataFrame:
    """
    Compute quarter-over-quarter AUM changes per scheme.

    Adds columns:
      - aum_qoq_change_cr  (absolute change in crores)
      - aum_qoq_pct        (% change)
    """
    df = aum_ts.copy()
    if aum_col not in df.columns:
        return df

    # Identifiers for a unique fund series
    group_cols = ["amc", "scheme_name"]
    if "scheme_code" in df.columns:
        group_cols.append("scheme_code")

    # Group by fund/scheme and calculate differences on the sorted time series
    # (ts should already be sorted by quarter via _sort_by_quarter)
    df["aum_qoq_change_cr"] = df.groupby(group_cols)[aum_col].diff()
    df["aum_qoq_pct"] = df.groupby(group_cols)[aum_col].pct_change() * 100
    df["aum_qoq_pct"] = df["aum_qoq_pct"].round(2)
    return df


# ─── Sub-scheme AUM split ─────────────────────────────────────────────────────

def subscheme_aum_split(
    quarter_df: pd.DataFrame,
    base_scheme_name: str,
) -> pd.DataFrame:
    """
    From a single quarter's AUM DataFrame, extract all sub-schemes for a fund.

    Sub-schemes are Direct/Regular × Growth/IDCW variants that share the base name.

    Returns a DataFrame with scheme_name, aum_cr, and inferred columns:
      - plan (Direct / Regular)
      - option (Growth / IDCW / Dividend)
    """
    scheme_col = _find_col(quarter_df, "scheme_name") or _find_col(quarter_df, "scheme")
    if not scheme_col:
        return pd.DataFrame()

    mask = quarter_df[scheme_col].str.contains(base_scheme_name, case=False, na=False)
    df = quarter_df[mask].copy()

    def _infer_plan(name: str) -> str:
        n = name.lower()
        if "direct" in n:
            return "Direct"
        if "regular" in n:
            return "Regular"
        return "Unknown"

    def _infer_option(name: str) -> str:
        n = name.lower()
        if "idcw" in n or "dividend" in n:
            return "IDCW/Dividend"
        if "growth" in n:
            return "Growth"
        return "Unknown"

    df["plan"] = df[scheme_col].apply(_infer_plan)
    df["option"] = df[scheme_col].apply(_infer_option)
    return df.reset_index(drop=True)
