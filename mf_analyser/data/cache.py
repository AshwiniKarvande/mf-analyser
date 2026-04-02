"""
cache.py — Local CSV cache layer for NAV and AUM data.

Strategy:
  - NAV CSVs stored at data/nav/<scheme_code>.csv
  - AUM CSVs stored at data/aum/<safe_quarter>.csv
  - Scheme list stored at data/scheme_codes.csv
  - Staleness checked via file mtime vs configured TTL
  - Pass force_refresh=True to bypass TTL
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from mf_analyser.config import (
    AUM_CACHE_TTL_DAYS,
    AUM_CACHE_DIR,
    NAV_CACHE_DIR,
    NAV_CACHE_TTL_HOURS,
    SCHEME_LIST_CACHE,
    SCHEME_LIST_TTL_DAYS,
    HOLDINGS_CACHE_DIR,
    HOLDINGS_CACHE_TTL_DAYS
)
from mf_analyser.data.fetcher import (
    FetchError,
    fetch_average_aum,
    fetch_nav_history,
    get_all_scheme_codes,
)
import json
from mf_analyser.data.holdings_fetcher import fetch_holdings as _fetch_holdings_from_groww

logger = logging.getLogger(__name__)


def _is_stale(path: Path, ttl_hours: float) -> bool:
    """Return True if the file doesn't exist or is older than ttl_hours."""
    if not path.exists():
        return True
    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    return age > timedelta(hours=ttl_hours)


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


# ─── NAV cache ────────────────────────────────────────────────────────────────

def get_nav(scheme_code: str | int, force_refresh: bool = False) -> pd.DataFrame:
    """
    Get NAV history for a scheme. Reads from local CSV cache if fresh.

    Returns a DataFrame with columns: date (datetime64), nav (float64)

    Args:
        scheme_code:    AMFI scheme code (string or int)
        force_refresh:  If True, always fetch from mftool regardless of cache age
    """
    code = str(scheme_code)
    _ensure_dir(NAV_CACHE_DIR)
    cache_path = NAV_CACHE_DIR / f"{code}.csv"

    stale = force_refresh or _is_stale(cache_path, NAV_CACHE_TTL_HOURS)

    if not stale:
        logger.debug("Cache hit for scheme %s at %s", code, cache_path)
        df = pd.read_csv(cache_path, parse_dates=["date"])
        df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
        return df.sort_values("date").reset_index(drop=True)

    logger.info("Fetching NAV for scheme %s from mftool…", code)
    df = fetch_nav_history(code)
    df.to_csv(cache_path, index=False)
    logger.info("Cached %d NAV records → %s", len(df), cache_path)
    return df


def clear_nav_cache(scheme_code: str | int) -> None:
    """Delete the cached NAV CSV for a scheme."""
    cache_path = NAV_CACHE_DIR / f"{scheme_code}.csv"
    if cache_path.exists():
        cache_path.unlink()
        logger.info("Cleared NAV cache for scheme %s", scheme_code)


def list_cached_navs() -> list[str]:
    """Return a list of scheme codes that have a local NAV cache."""
    if not NAV_CACHE_DIR.exists():
        return []
    return [p.stem for p in NAV_CACHE_DIR.glob("*.csv")]


# ─── AUM cache ────────────────────────────────────────────────────────────────

def _quarter_to_filename(quarter: str) -> str:
    """Convert 'Jan-Mar 2024' → 'Jan-Mar_2024' for safe file naming."""
    return quarter.replace(" ", "_")


def get_aum(quarter: str, force_refresh: bool = False) -> pd.DataFrame:
    """
    Get average AUM data for a quarter. Reads from local CSV cache if fresh.

    Args:
        quarter:        e.g. "Jan-Mar 2024"
        force_refresh:  bypass cache TTL
    """
    _ensure_dir(AUM_CACHE_DIR)
    cache_path = AUM_CACHE_DIR / f"{_quarter_to_filename(quarter)}.csv"
    ttl_hours = AUM_CACHE_TTL_DAYS * 24

    stale = force_refresh or _is_stale(cache_path, ttl_hours)

    if not stale:
        logger.debug("Cache hit for AUM quarter %s", quarter)
        return pd.read_csv(cache_path)

    logger.info("Fetching AUM for quarter %s from mftool…", quarter)
    df = fetch_average_aum(quarter)
    df.to_csv(cache_path, index=False)
    logger.info("Cached %d AUM records → %s", len(df), cache_path)
    return df


# ─── Scheme list cache ────────────────────────────────────────────────────────

def get_scheme_list(force_refresh: bool = False) -> pd.DataFrame:
    """
    Get all AMFI scheme codes. Reads from local CSV cache if fresh.

    Returns DataFrame with columns: scheme_code, scheme_name
    """
    _ensure_dir(SCHEME_LIST_CACHE.parent)
    ttl_hours = SCHEME_LIST_TTL_DAYS * 24
    stale = force_refresh or _is_stale(SCHEME_LIST_CACHE, ttl_hours)

    if not stale:
        logger.debug("Cache hit for scheme list")
        return pd.read_csv(SCHEME_LIST_CACHE, dtype=str)

    logger.info("Fetching full scheme list from mftool…")
    df = get_all_scheme_codes()
    df.to_csv(SCHEME_LIST_CACHE, index=False)
    logger.info("Cached %d schemes → %s", len(df), SCHEME_LIST_CACHE)
    return df


def search_cached_schemes(query: str, top_n: int = 20) -> pd.DataFrame:
    """
    Search the (cached) scheme list by name. Falls back to live fetch if needed.
    """
    df = get_scheme_list()
    mask = df["scheme_name"].str.contains(query, case=False, na=False)
    return df[mask].head(top_n).reset_index(drop=True)


# ─── Holdings cache ──────────────────────────────────────────────────────────

def get_holdings(scheme_code: str | int, force_refresh: bool = False, slug: str | None = None) -> dict:
    """
    Get portfolio holdings for a scheme. Reads from local JSON cache if fresh.
    
    Args:
        scheme_code:    AMFI scheme code
        force_refresh:  bypass cache TTL
        slug:           optional custom Groww slug
    """
    _ensure_dir(HOLDINGS_CACHE_DIR)
    code = str(scheme_code)
    # We store multiple files with dates to allow history, but 'latest' for quick access
    # Actually, for simpler caching, use code.json
    cache_path = HOLDINGS_CACHE_DIR / f"{code}.json"
    ttl_hours = HOLDINGS_CACHE_TTL_DAYS * 24

    stale = force_refresh or _is_stale(cache_path, ttl_hours)

    if not stale:
        logger.debug("Cache hit for holdings of scheme %s", code)
        with open(cache_path, "r") as f:
            return json.load(f)

    logger.info("Fetching holdings for scheme %s from Groww…", code)
    try:
        data = _fetch_holdings_from_groww(code, slug=slug)
        # Add a fetch timestamp
        data["fetched_at"] = datetime.now().isoformat()
        
        with open(cache_path, "w") as f:
            json.dump(data, f, indent=4)
        
        # Also store a historical copy: code_YYYYMMDD.json
        date_str = datetime.now().strftime("%Y%m%d")
        hist_path = HOLDINGS_CACHE_DIR / f"{code}_{date_str}.json"
        with open(hist_path, "w") as f:
            json.dump(data, f, indent=4)
            
        logger.info("Cached holdings records → %s", cache_path)
        return data
    except Exception as e:
        logger.error("Failed to fetch holdings for %s: %s", code, str(e))
        if cache_path.exists():
            logger.warning("Returning stale holdings cache due to fetch error.")
            with open(cache_path, "r") as f:
                return json.load(f)
        raise
