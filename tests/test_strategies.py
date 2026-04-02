"""Tests for investment strategy backtests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from mf_analyser.analysis.strategies import (
    StrategyResult,
    compare_strategies,
    lump_sum,
    momentum_ma,
    sip,
    sip_with_stop_loss,
    value_averaging,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def rising_nav() -> pd.DataFrame:
    """Steadily rising NAV: 100 → 200 over 5 years (business days)."""
    dates = pd.date_range("2019-01-01", "2023-12-31", freq="B")
    navs = np.linspace(100.0, 200.0, len(dates))
    return pd.DataFrame({"date": dates, "nav": navs})


@pytest.fixture
def flat_nav() -> pd.DataFrame:
    dates = pd.date_range("2020-01-01", "2022-12-31", freq="B")
    return pd.DataFrame({"date": dates, "nav": [100.0] * len(dates)})


# ─── Lump Sum ─────────────────────────────────────────────────────────────────

def test_lump_sum_basic(rising_nav):
    result = lump_sum(rising_nav, amount=100_000)
    assert isinstance(result, StrategyResult)
    assert result.total_invested == pytest.approx(100_000)
    assert result.final_value > result.total_invested   # NAV doubled, should profit


def test_lump_sum_flat(flat_nav):
    result = lump_sum(flat_nav, amount=50_000)
    assert result.absolute_return_pct == pytest.approx(0.0, abs=0.1)
    assert result.cagr_pct == pytest.approx(0.0, abs=0.1)


def test_lump_sum_result_has_transaction(rising_nav):
    result = lump_sum(rising_nav, amount=10_000)
    assert len(result.transactions) == 1
    assert result.transactions.iloc[0]["type"] == "BUY"


# ─── SIP ──────────────────────────────────────────────────────────────────────

def test_sip_basic(rising_nav):
    result = sip(rising_nav, monthly_amount=5_000)
    assert result.total_invested > 0
    assert result.final_value > 0
    assert len(result.transactions) > 1   # Multiple months


def test_sip_monthly_count(rising_nav):
    result = sip(rising_nav, monthly_amount=5_000,
                  start_date="2020-01-01", end_date="2022-12-31")
    # ~36 months
    assert 30 <= len(result.transactions) <= 40


def test_sip_positive_return_on_rising_nav(rising_nav):
    result = sip(rising_nav, monthly_amount=5_000)
    assert result.cagr_pct > 0


# ─── Value Averaging ──────────────────────────────────────────────────────────

def test_value_averaging_basic(rising_nav):
    result = value_averaging(rising_nav, monthly_target_growth=1.0, start_amount=5_000)
    assert result.total_invested > 0
    assert result.final_value > 0


def test_value_averaging_has_transactions(rising_nav):
    result = value_averaging(rising_nav, monthly_target_growth=1.0, start_amount=5_000)
    assert len(result.transactions) > 1


# ─── Momentum MA ──────────────────────────────────────────────────────────────

def test_momentum_ma_basic(rising_nav):
    result = momentum_ma(rising_nav, amount=100_000, fast_window=20, slow_window=50)
    assert isinstance(result, StrategyResult)
    assert result.total_invested == pytest.approx(100_000)


def test_momentum_ma_rising_nav_profitable(rising_nav):
    """On a steadily rising NAV, fast MA stays above slow — should stay invested."""
    result = momentum_ma(rising_nav, amount=100_000, fast_window=20, slow_window=50)
    assert result.final_value > 0


# ─── SIP + Stop-Loss ──────────────────────────────────────────────────────────

def test_sip_stoploss_basic(rising_nav):
    result = sip_with_stop_loss(rising_nav, monthly_amount=5_000, stop_loss_pct=20)
    assert isinstance(result, StrategyResult)
    assert result.total_invested > 0


def test_sip_stoploss_no_trigger_on_rising(rising_nav):
    """On steadily rising NAV, stop-loss should never trigger."""
    result = sip_with_stop_loss(rising_nav, monthly_amount=5_000, stop_loss_pct=20)
    sl_txns = result.transactions[result.transactions["type"] == "STOP-LOSS-SELL"]
    assert len(sl_txns) == 0


# ─── compare_strategies ───────────────────────────────────────────────────────

def test_compare_strategies(rising_nav):
    r1 = lump_sum(rising_nav, amount=100_000)
    r2 = sip(rising_nav, monthly_amount=5_000)
    summary = compare_strategies([r1, r2])
    assert len(summary) == 2
    assert "strategy" in summary.columns
    assert "cagr_pct" in summary.columns
