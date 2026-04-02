"""
comparison.py — Mutual fund peer discovery and performance comparison.

Features:
  - Auto-identify category from scheme details.
  - Keyword-based search for peers in the same category.
  - Filtering for 'Direct' and 'Growth' variants.
  - Performance comparison across 1Y, 3Y, 5Y, and 10Y.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from mf_analyser.analysis.returns import cagr, max_drawdown
from mf_analyser.data.cache import get_nav, search_cached_schemes
from mf_analyser.data.fetcher import fetch_scheme_details

logger = logging.getLogger(__name__)


# ─── Peer Discovery ───────────────────────────────────────────────────────────

def discover_peers(scheme_code: str | int, limit: int = 5) -> list[tuple[str, str]]:
    """
    Find top 5 peers for a given fund by identifying its category and search.

    Args:
        scheme_code: AMFI scheme code of the target fund.
        limit:       Number of peers to return (excluding the target itself).
    """
    code = str(scheme_code)
    try:
        details = fetch_scheme_details(code)
    except Exception as exc:
        logger.error("Could not fetch details for scheme %s: %s", code, exc)
        return []

    category: str = details.get("scheme_category", "")
    if not category:
        logger.warning("No category found for scheme %s", code)
        return []

    # Extract keywords from category string, e.g. "Equity Scheme - Mid Cap Fund" -> "Mid Cap"
    # Common format: "Equity Scheme - <Category Name> Fund"
    keyword = category.replace("Equity Scheme -", "").replace("Fund", "").strip()
    if not keyword:
        return []

    logger.info("Category: %-20s | Keyword: %s", category, keyword)

    # Search the scheme list for matches
    # search_cached_schemes returns a DF with scheme_code, scheme_name
    potential_peers = search_cached_schemes(keyword, top_n=50)

    # Filter for "Direct" and "Growth" to ensure apples-to-apples comparison
    def _is_direct_growth(name: str) -> bool:
        n = name.lower()
        # Look for BOTH 'direct' AND 'growth'
        # Also exclude the current fund by checking if the code is different (done later)
        return "direct" in n and ("growth" in n or "gr" in n)

    mask = potential_peers["scheme_name"].apply(_is_direct_growth)
    peers_df = potential_peers[mask].copy()

    # Exclude the source fund itself
    peers_df = peers_df[peers_df["scheme_code"] != code]

    # Return top N as (code, name) tuples
    results = peers_df.head(limit).values.tolist()
    return [(str(r[0]), str(r[1])) for r in results]


# ─── Multi-fund Comparison ──────────────────────────────────────────────────

def compare_returns(
    scheme_codes: list[str],
    periods: list[str] = ["1Y", "3Y", "5Y", "10Y"],
) -> pd.DataFrame:
    """
    Compare performance metrics for a list of fund codes.

    Args:
        scheme_codes: List of AMFI scheme codes.
        periods:      CAGR periods to include.
    """

    def _fetch_metrics(code: str) -> dict | None:
        try:
            # Use get_nav (cached)
            nav_df = get_nav(code)
            if nav_df.empty:
                return None

            row = {
                "scheme_code": code,
                "scheme_name": "",  # To be filled by caller or details
            }

            # CAGR for each period
            from datetime import date, timedelta
            latest_date = nav_df["date"].max().date()

            period_map = {
                "1Y": 365,
                "3Y": 1095,
                "5Y": 1825,
                "10Y": 3652,
            }

            for p in periods:
                days = period_map.get(p, 365)
                start = latest_date - timedelta(days=days)
                if start >= nav_df["date"].min().date():
                    r = cagr(nav_df, start_date=start, end_date=latest_date)
                    row[f"{p}_cagr_pct"] = r.get("cagr_pct", None)
                else:
                    row[f"{p}_cagr_pct"] = None

            # Add Max Drawdown
            dd = max_drawdown(nav_df)
            row["max_drawdown_pct"] = dd["drawdown_pct"]

            return row
        except Exception as exc:
            logger.error("Error computing comparison for %s: %s", code, exc)
            return None

    # Fetch in parallel using Threads
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(_fetch_metrics, scheme_codes))

    # Build DataFrame
    final_rows = [r for r in results if r is not None]
    if not final_rows:
        return pd.DataFrame()

    return pd.DataFrame(final_rows)
