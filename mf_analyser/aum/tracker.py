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

def generate_quarters(start_year: int = 2020, end_year: int | None = None) -> list[str]:
    """
    Generate a list of quarter strings from start_year to end_year (inclusive).

    Format: "Jan-Mar 2020", "Apr-Jun 2020", "Jul-Sep 2020", "Oct-Dec 2020"
    """
    import datetime
    if end_year is None:
        end_year = datetime.date.today().year

    labels = {1: "Jan-Mar", 2: "Apr-Jun", 3: "Jul-Sep", 4: "Oct-Dec"}
    quarters = []
    for year in range(start_year, end_year + 1):
        for q, label in labels.items():
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
    start_year: int = 2020,
    end_year: int | None = None,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Build AUM time series for a specific scheme (matched by name substring).

    Returns a DataFrame with columns: quarter, scheme_name, aum_cr
    One row per quarter where data is available.
    """
    quarters = generate_quarters(start_year, end_year)
    ts = build_aum_timeseries(
        quarters,
        scheme_filter=scheme_name_query,
        force_refresh=force_refresh,
    )

    if ts.empty:
        return ts

    # Normalise column names
    scheme_col = _find_col(ts, "scheme_name") or _find_col(ts, "scheme")
    aum_col = _find_col(ts, "aum")

    keep = ["quarter"]
    if scheme_col:
        keep.append(scheme_col)
    if aum_col:
        keep.append(aum_col)

    ts = ts[keep].drop_duplicates()
    return ts


# ─── AUM growth metrics ───────────────────────────────────────────────────────

def aum_growth_summary(aum_ts: pd.DataFrame, aum_col: str = "aum_cr") -> pd.DataFrame:
    """
    Compute quarter-over-quarter AUM changes.

    Adds columns:
      - aum_qoq_change_cr  (absolute change in crores)
      - aum_qoq_pct        (% change)
    """
    df = aum_ts.copy()
    if aum_col not in df.columns:
        return df

    df["aum_qoq_change_cr"] = df[aum_col].diff()
    df["aum_qoq_pct"] = df[aum_col].pct_change() * 100
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
