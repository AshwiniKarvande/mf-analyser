"""Tests for returns calculation functions."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from mf_analyser.analysis.returns import (
    absolute_return,
    cagr,
    max_drawdown,
    returns_table,
    rolling_returns,
    rolling_returns_summary,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def simple_nav() -> pd.DataFrame:
    """5-year NAV series doubling linearly from 100 to 200."""
    dates = pd.date_range("2019-01-01", "2023-12-31", freq="B")
    start, end = 100.0, 200.0
    navs = np.linspace(start, end, len(dates))
    return pd.DataFrame({"date": dates, "nav": navs})


@pytest.fixture
def flat_nav() -> pd.DataFrame:
    """Flat NAV series — zero return."""
    dates = pd.date_range("2020-01-01", "2023-12-31", freq="B")
    return pd.DataFrame({"date": dates, "nav": [100.0] * len(dates)})


# ─── absolute_return ──────────────────────────────────────────────────────────

def test_absolute_return_full_period(simple_nav):
    result = absolute_return(simple_nav)
    assert result["start_nav"] == pytest.approx(100.0, abs=1.0)
    assert result["end_nav"] == pytest.approx(200.0, abs=1.0)
    assert result["absolute_return_pct"] == pytest.approx(100.0, abs=2.0)


def test_absolute_return_date_range(simple_nav):
    result = absolute_return(simple_nav, start_date="2019-01-01", end_date="2020-01-01")
    assert result["days"] > 300


def test_absolute_return_flat(flat_nav):
    result = absolute_return(flat_nav)
    assert result["absolute_return_pct"] == pytest.approx(0.0, abs=0.01)


# ─── cagr ─────────────────────────────────────────────────────────────────────

def test_cagr_roughly_correct(simple_nav):
    """NAV doubles in ~5 years → CAGR ~15%."""
    result = cagr(simple_nav)
    assert 12.0 <= result["cagr_pct"] <= 18.0


def test_cagr_flat_returns_zero(flat_nav):
    result = cagr(flat_nav)
    assert result["cagr_pct"] == pytest.approx(0.0, abs=0.1)


def test_cagr_includes_years(simple_nav):
    result = cagr(simple_nav)
    assert result["years"] == pytest.approx(5.0, abs=0.2)


# ─── rolling_returns ──────────────────────────────────────────────────────────

def test_rolling_returns_shape(simple_nav):
    rdf = rolling_returns(simple_nav, window_years=1)
    assert "rolling_1y_cagr_pct" in rdf.columns
    assert len(rdf) == len(simple_nav)


def test_rolling_returns_nan_at_start(simple_nav):
    rdf = rolling_returns(simple_nav, window_years=2)
    # First 2 years should be NaN
    first_valid = rdf["rolling_2y_cagr_pct"].first_valid_index()
    assert first_valid > 0


# ─── rolling_returns_summary ──────────────────────────────────────────────────

def test_rolling_summary_keys(simple_nav):
    summary = rolling_returns_summary(simple_nav, window_years=1)
    for key in ["min_pct", "max_pct", "mean_pct", "median_pct", "p10_pct", "p90_pct"]:
        assert key in summary


# ─── returns_table ────────────────────────────────────────────────────────────

def test_returns_table_columns(simple_nav):
    rt = returns_table(simple_nav)
    assert "period" in rt.columns
    assert "cagr_pct" in rt.columns
    assert "absolute_pct" in rt.columns


def test_returns_table_has_rows(simple_nav):
    rt = returns_table(simple_nav)
    assert len(rt) > 0


# ─── max_drawdown ─────────────────────────────────────────────────────────────

def test_max_drawdown_flat_nav(flat_nav):
    dd = max_drawdown(flat_nav)
    assert dd["drawdown_pct"] == pytest.approx(0.0, abs=0.01)


def test_max_drawdown_with_dip():
    """NAV goes 100 → 150 → 75 → 120. Drawdown = 50%."""
    dates = pd.date_range("2020-01-01", periods=4, freq="MS")
    navs = [100.0, 150.0, 75.0, 120.0]
    df = pd.DataFrame({"date": dates, "nav": navs})
    dd = max_drawdown(df)
    assert dd["drawdown_pct"] == pytest.approx(-50.0, abs=1.0)
    assert dd["trough_nav"] == pytest.approx(75.0, abs=0.1)
