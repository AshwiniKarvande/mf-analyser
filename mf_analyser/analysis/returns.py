"""
returns.py — Mutual fund return calculations.

All functions accept a NAV DataFrame with columns:
  - date  (datetime64)
  - nav   (float64)

Sorted ascending by date (guaranteed by cache.get_nav).
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd


# ─── Point-to-point helpers ───────────────────────────────────────────────────

def _nearest_nav(df: pd.DataFrame, target: date) -> tuple[date, float]:
    """Return the closest available (date, nav) to a target date."""
    target_ts = pd.Timestamp(target)
    idx = (df["date"] - target_ts).abs().idxmin()
    row = df.loc[idx]
    return row["date"].date(), float(row["nav"])


def absolute_return(
    df: pd.DataFrame,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
) -> dict:
    """
    Compute absolute return between two dates.

    Returns:
        {
          start_date, start_nav,
          end_date, end_nav,
          absolute_return_pct,
          gain_loss,
          days
        }
    """
    if isinstance(start_date, str):
        start_date = date.fromisoformat(start_date)
    if isinstance(end_date, str):
        end_date = date.fromisoformat(end_date)

    if start_date is None:
        start_date = df["date"].min().date()
    if end_date is None:
        end_date = df["date"].max().date()

    s_date, s_nav = _nearest_nav(df, start_date)
    e_date, e_nav = _nearest_nav(df, end_date)

    abs_ret = (e_nav - s_nav) / s_nav * 100
    days = (e_date - s_date).days

    return {
        "start_date": s_date,
        "start_nav": round(s_nav, 4),
        "end_date": e_date,
        "end_nav": round(e_nav, 4),
        "absolute_return_pct": round(abs_ret, 2),
        "gain_loss_pct": round(abs_ret, 2),
        "days": days,
    }


def cagr(
    df: pd.DataFrame,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
) -> dict:
    """
    Compute CAGR (Compound Annual Growth Rate) between two dates.

    Formula: ((end_nav / start_nav) ^ (1 / years)) - 1
    """
    result = absolute_return(df, start_date, end_date)
    years = result["days"] / 365.25

    if years <= 0:
        result["cagr_pct"] = 0.0
        result["years"] = 0.0
        return result

    cagr_val = ((result["end_nav"] / result["start_nav"]) ** (1 / years) - 1) * 100
    result["cagr_pct"] = round(cagr_val, 2)
    result["years"] = round(years, 2)
    return result


# ─── Rolling returns ──────────────────────────────────────────────────────────

def rolling_returns(
    df: pd.DataFrame,
    window_years: int = 3,
    return_type: str = "cagr",  # "cagr" or "absolute"
) -> pd.DataFrame:
    """
    Compute rolling returns for every date in the NAV series.

    Args:
        window_years:   Look-back window in years (e.g. 1, 3, 5)
        return_type:    "cagr" or "absolute"

    Returns:
        DataFrame with columns: date, nav, return_pct
        (NaN for dates where look-back is unavailable)
    """
    window_days = int(window_years * 365.25)
    df = df.copy().sort_values("date").reset_index(drop=True)
    df = df.set_index("date")

    returns: list[float | None] = []

    for ts, row in df.iterrows():
        past_ts = ts - pd.Timedelta(days=window_days)
        past_candidates = df[df.index <= past_ts]
        if past_candidates.empty:
            returns.append(np.nan)
            continue

        past_nav = float(past_candidates.iloc[-1]["nav"])
        curr_nav = float(row["nav"])
        years = (ts - past_candidates.index[-1]).days / 365.25

        if return_type == "cagr" and years > 0:
            ret = ((curr_nav / past_nav) ** (1 / years) - 1) * 100
        else:
            ret = (curr_nav - past_nav) / past_nav * 100

        returns.append(round(ret, 2))

    df = df.reset_index()
    df[f"rolling_{window_years}y_{return_type}_pct"] = returns
    return df


def rolling_returns_summary(
    df: pd.DataFrame,
    window_years: int = 3,
) -> dict:
    """
    Summary statistics for rolling CAGR over a given window.

    Returns min, max, mean, median, percentile-10, percentile-25, percentile-75.
    """
    rdf = rolling_returns(df, window_years=window_years, return_type="cagr")
    col = f"rolling_{window_years}y_cagr_pct"
    series = rdf[col].dropna()

    return {
        "window_years": window_years,
        "count": len(series),
        "min_pct": round(float(series.min()), 2),
        "max_pct": round(float(series.max()), 2),
        "mean_pct": round(float(series.mean()), 2),
        "median_pct": round(float(series.median()), 2),
        "p10_pct": round(float(series.quantile(0.10)), 2),
        "p25_pct": round(float(series.quantile(0.25)), 2),
        "p75_pct": round(float(series.quantile(0.75)), 2),
        "p90_pct": round(float(series.quantile(0.90)), 2),
    }


# ─── Multi-period returns table ───────────────────────────────────────────────

STANDARD_PERIODS = {
    "1M": 30,
    "3M": 90,
    "6M": 180,
    "1Y": 365,
    "2Y": 730,
    "3Y": 1095,
    "5Y": 1825,
    "7Y": 2555,
    "10Y": 3650,
}


def returns_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute absolute and CAGR returns for standard trailing periods.

    Returns a DataFrame with columns:
      period, start_date, start_nav, end_date, end_nav,
      absolute_pct, cagr_pct, days
    """
    latest_date = df["date"].max().date()
    rows = []

    for label, days in STANDARD_PERIODS.items():
        start = latest_date - timedelta(days=days)
        if start < df["date"].min().date():
            continue
        r = cagr(df, start_date=start, end_date=latest_date)
        rows.append({
            "period": label,
            "start_date": r["start_date"],
            "start_nav": r["start_nav"],
            "end_date": r["end_date"],
            "end_nav": r["end_nav"],
            "absolute_pct": r["absolute_return_pct"],
            "cagr_pct": r.get("cagr_pct", np.nan),
            "days": r["days"],
        })

    return pd.DataFrame(rows)


# ─── Drawdown analysis ────────────────────────────────────────────────────────

def max_drawdown(df: pd.DataFrame) -> dict:
    """
    Compute maximum drawdown: peak-to-trough decline in NAV.

    Returns:
        {
          peak_date, peak_nav,
          trough_date, trough_nav,
          drawdown_pct,
          recovery_date (or None if not recovered)
        }
    """
    df = df.copy().sort_values("date").reset_index(drop=True)
    nav = df["nav"].values
    dates = df["date"].values

    rolling_max = np.maximum.accumulate(nav)
    drawdowns = (nav - rolling_max) / rolling_max * 100

    trough_idx = int(np.argmin(drawdowns))
    peak_idx = int(np.argmax(nav[: trough_idx + 1]))
    dd_pct = round(float(drawdowns[trough_idx]), 2)

    # Check if recovered
    recovery_date = None
    peak_nav_val = float(nav[peak_idx])
    post_trough = df.iloc[trough_idx:]
    recovered = post_trough[post_trough["nav"] >= peak_nav_val]
    if not recovered.empty:
        recovery_date = recovered.iloc[0]["date"].date()

    return {
        "peak_date": pd.Timestamp(dates[peak_idx]).date(),
        "peak_nav": round(peak_nav_val, 4),
        "trough_date": pd.Timestamp(dates[trough_idx]).date(),
        "trough_nav": round(float(nav[trough_idx]), 4),
        "drawdown_pct": dd_pct,
        "recovery_date": recovery_date,
    }
