"""
fetcher.py — mftool wrapper with error handling.

All public functions return pandas DataFrames or dicts.
Network errors raise FetchError so callers can handle gracefully.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.error import URLError

import pandas as pd
from mftool import Mftool

logger = logging.getLogger(__name__)

_mf = Mftool()


class FetchError(RuntimeError):
    """Raised when mftool fails to fetch data."""


# ─── Scheme discovery ─────────────────────────────────────────────────────────

def get_all_scheme_codes() -> pd.DataFrame:
    """
    Return a DataFrame of all AMFI scheme codes and names.

    Columns: scheme_code, scheme_name
    """
    try:
        codes: dict = _mf.get_scheme_codes()
    except (URLError, Exception) as exc:
        raise FetchError(f"Failed to fetch scheme codes: {exc}") from exc

    df = pd.DataFrame(list(codes.items()), columns=["scheme_code", "scheme_name"])
    df["scheme_code"] = df["scheme_code"].astype(str)
    return df.sort_values("scheme_code").reset_index(drop=True)


def search_schemes(query: str, top_n: int = 20) -> pd.DataFrame:
    """
    Search for schemes whose name contains *query* (case-insensitive).

    Returns a DataFrame with columns: scheme_code, scheme_name
    """
    all_df = get_all_scheme_codes()
    mask = all_df["scheme_name"].str.contains(query, case=False, na=False)
    results = all_df[mask].head(top_n).reset_index(drop=True)
    return results


# ─── NAV history ──────────────────────────────────────────────────────────────

def fetch_nav_history(scheme_code: str | int) -> pd.DataFrame:
    """
    Fetch full NAV history for a given scheme code.

    Returns a DataFrame with columns:
      - date (datetime64)
      - nav  (float64)

    Sorted ascending by date.
    """
    code = str(scheme_code)
    try:
        data = _mf.get_scheme_historical_nav(code, as_Dataframe=True)
    except (URLError, Exception) as exc:
        raise FetchError(f"Failed to fetch NAV for scheme {code}: {exc}") from exc

    if data is None or (isinstance(data, pd.DataFrame) and data.empty):
        raise FetchError(f"No NAV data returned for scheme {code}")

    df: pd.DataFrame = data.copy()

    # mftool sometimes returns the date as the index
    if "date" not in df.columns and df.index.name and df.index.name.lower() == "date":
        df = df.reset_index()

    # mftool returns columns: date, nav (sometimes as strings)
    df.columns = [c.lower().strip() for c in df.columns]
    if "date" not in df.columns or "nav" not in df.columns:
        raise FetchError(f"Unexpected columns from mftool: {list(df.columns)}")

    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    df = df.dropna(subset=["date", "nav"])
    df = df.sort_values("date").reset_index(drop=True)
    return df[["date", "nav"]]


# ─── Scheme details ───────────────────────────────────────────────────────────

def fetch_scheme_details(scheme_code: str | int) -> dict[str, Any]:
    """
    Fetch metadata for a scheme: name, AMC, category, start date, etc.
    """
    code = str(scheme_code)
    try:
        details = _mf.get_scheme_details(code)
    except (URLError, Exception) as exc:
        raise FetchError(f"Failed to fetch details for scheme {code}: {exc}") from exc

    if not details:
        raise FetchError(f"No details returned for scheme {code}")

    return dict(details)


def fetch_scheme_quote(scheme_code: str | int) -> dict[str, Any]:
    """
    Fetch latest NAV quote: scheme name, NAV, last updated date.
    """
    code = str(scheme_code)
    try:
        quote = _mf.get_scheme_quote(code)
    except (URLError, Exception) as exc:
        raise FetchError(f"Failed to fetch quote for scheme {code}: {exc}") from exc

    return dict(quote or {})


# ─── AUM ──────────────────────────────────────────────────────────────────────

def fetch_average_aum(quarter: str) -> pd.DataFrame:
    """
    Fetch average AUM data for a given quarter.

    quarter format: "Jan-Mar 2024", "Apr-Jun 2024", "Jul-Sep 2024", "Oct-Dec 2024"

    Returns a DataFrame with columns:
      amc, scheme_name, scheme_code, aum_cr (AUM in crores)
    """
    try:
        data = _mf.get_average_aum(quarter, as_json=False)
    except (URLError, Exception) as exc:
        raise FetchError(f"Failed to fetch AUM for quarter {quarter!r}: {exc}") from exc

    if not data:
        raise FetchError(f"No AUM data returned for quarter {quarter!r}")

    # mftool returns a list of dicts
    df = pd.DataFrame(data)
    df.columns = [c.lower().strip().replace(" ", "_") for c in df.columns]

    # Normalise common column patterns
    aum_col = next((c for c in df.columns if "aum" in c), None)
    if aum_col:
        df.rename(columns={aum_col: "aum_cr"}, inplace=True)
        df["aum_cr"] = pd.to_numeric(df["aum_cr"], errors="coerce")

    df["quarter"] = quarter
    return df
