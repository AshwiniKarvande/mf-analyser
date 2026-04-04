"""
fetcher.py — mftool wrapper with error handling.

All public functions return pandas DataFrames or dicts.
Network errors raise FetchError so callers can handle gracefully.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.error import URLError

import pandas as pd
import requests
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


# ─── New AUM API Constants ──────────────────────────────────────────────────

AMC_IDS = [
    3, 53, 1, 4, 59, 46, 32, 6, 47, 54, 27, 9, 37, 20, 57, 48, 68, 62, 65, 63,
    42, 70, 16, 17, 56, 18, 69, 45, 55, 21, 58, 64, 10, 13, 35, 22, 66, 33, 25,
    26, 61, 28, 71
]

AUM_API_URL = "https://www.amfiindia.com/api/average-aum-schemewise"


def _map_quarter_to_amfi_params(quarter: str) -> tuple[int, int]:
    """
    Map quarter string to AMFI's fyId and periodId.
    Example: 'Jan-Mar 2024' -> (3, 1)

    fyId mapping:
    1: 2025-2026
    2: 2024-2025
    3: 2023-2024 (ends March 2024)

    periodId mapping:
    1: Jan - March
    2: Oct - December
    3: July - September
    4: April - June
    """
    match = re.search(r"(Jan|Apr|Jul|Oct).*(?:\s|-)([23][0-9]{3})", quarter, re.I)
    if not match:
        raise FetchError(f"Invalid quarter format: {quarter!r}. Expected e.g. 'Jan-Mar 2024'")

    month_shorthand = match.group(1).lower()
    year = int(match.group(2))

    # Financial Year Logic
    # Jan-Mar 2024 belongs to FY 2023-24
    if month_shorthand == "jan":
        fy_year = year - 1
        period_id = 1
    elif month_shorthand == "oct":
        fy_year = year
        period_id = 2
    elif month_shorthand == "jul":
        fy_year = year
        period_id = 3
    elif month_shorthand == "apr":
        fy_year = year
        period_id = 4
    else:
        raise FetchError(f"Could not map quarter months: {quarter}")

    # fyId mapping relative to base 2025 (fyId=1)
    fy_id = 2025 - fy_year + 1
    if fy_id < 1:
        # If it's a future year, we still try 1
        fy_id = 1

    return fy_id, period_id


def fetch_average_aum(quarter: str) -> pd.DataFrame:
    """
    Fetch average AUM data for a given quarter using the new AMFI REST API.

    quarter format: "Jan-Mar 2024", "Apr-Jun 2024", etc.

    Returns a DataFrame with columns:
      amc, scheme_name, scheme_code, aum_cr (AUM in crores)
    """
    fy_id, period_id = _map_quarter_to_amfi_params(quarter)
    all_data = []

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    logger.info("Fetching AUM for quarter %s (fyId=%d, periodId=%d)", quarter, fy_id, period_id)

    # We iterate through known AMC IDs as the API requires MF_ID
    for mf_id in AMC_IDS:
        params = {
            "strType": "Typewise",
            "fyId": fy_id,
            "periodId": period_id,
            "MF_ID": mf_id
        }
        try:
            r = requests.get(AUM_API_URL, params=params, headers=headers, timeout=10)
            if r.status_code != 200:
                logger.warning("Failed to fetch AUM for MF_ID=%d (Status=%d)", mf_id, r.status_code)
                continue

            resp = r.json()
            data_list = resp.get("data", [])
            if not data_list:
                continue

            amc_name = data_list[0].get("Mfname", "Unknown")
            for record in data_list:
                for scheme in record.get("schemes", []):
                    aum_val = scheme.get("AverageAumForTheMonth", {}).get(
                        "ExcludingFundOfFundsDomesticButIncludingFundOfFundsOverseas", 0
                    )
                    all_data.append({
                        "amc": amc_name,
                        "scheme_name": scheme.get("SchemeNAVName"),
                        "scheme_code": str(scheme.get("AMFI_Code")),
                        "aum_cr": float(aum_val) / 100.0,  # Lakhs to Crores
                        "quarter": quarter
                    })

        except Exception as exc:
            logger.error("Error fetching AUM for MF_ID=%d: %s", mf_id, exc)

    if not all_data:
        raise FetchError(f"No AUM data returned for quarter {quarter!r} from AMFI API")

    return pd.DataFrame(all_data)
