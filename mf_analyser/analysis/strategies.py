"""
strategies.py — Investment strategy backtesting on historical NAV data.

All strategies accept a NAV DataFrame (date, nav) sorted ascending and return
a standardised StrategyResult dataclass with portfolio metrics.

Supported strategies:
  1. Lump Sum (one-time investment)
  2. SIP      (Systematic Investment Plan — monthly)
  3. STP      (Systematic Transfer Plan simulation)
  4. Value Averaging
  5. Momentum (MA crossover — buy/hold/sell based on moving average)
  6. DCA + Stop-Loss (SIP with a configurable stop-loss trigger)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable

import numpy as np
import pandas as pd


# ─── Result dataclass ─────────────────────────────────────────────────────────

@dataclass
class StrategyResult:
    """Standardised output for any backtest strategy."""

    strategy_name: str
    start_date: date
    end_date: date

    total_invested: float       # Total ₹ deployed
    final_value: float          # Portfolio value at end_date
    total_units: float          # Units held at end_date
    final_nav: float

    absolute_return_pct: float
    cagr_pct: float
    years: float

    # Detailed transaction log
    transactions: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def gain_loss(self) -> float:
        return round(self.final_value - self.total_invested, 2)

    def summary(self) -> dict:
        return {
            "strategy": self.strategy_name,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "invested_rs": round(self.total_invested, 2),
            "final_value_rs": round(self.final_value, 2),
            "gain_loss_rs": self.gain_loss,
            "absolute_return_pct": round(self.absolute_return_pct, 2),
            "cagr_pct": round(self.cagr_pct, 2),
            "years": round(self.years, 2),
            "total_units": round(self.total_units, 4),
            "final_nav": round(self.final_nav, 4),
        }


def _compute_cagr(invested: float, final: float, days: int) -> float:
    if days <= 0 or invested <= 0:
        return 0.0
    years = days / 365.25
    return round(((final / invested) ** (1 / years) - 1) * 100, 2)


def _filter_date_range(
    df: pd.DataFrame,
    start_date: date | str | None,
    end_date: date | str | None,
) -> pd.DataFrame:
    if isinstance(start_date, str):
        start_date = date.fromisoformat(start_date)
    if isinstance(end_date, str):
        end_date = date.fromisoformat(end_date)

    df = df.copy().sort_values("date").reset_index(drop=True)
    if start_date:
        df = df[df["date"] >= pd.Timestamp(start_date)]
    if end_date:
        df = df[df["date"] <= pd.Timestamp(end_date)]
    return df.reset_index(drop=True)


# ─── 1. Lump Sum ─────────────────────────────────────────────────────────────

def lump_sum(
    df: pd.DataFrame,
    amount: float,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
) -> StrategyResult:
    """
    One-time investment of `amount` at the earliest available date on/after start_date.

    Args:
        df:           NAV DataFrame (date, nav)
        amount:       ₹ to invest
        start_date:   Investment date (or earliest available)
        end_date:     Valuation date (or latest available)
    """
    data = _filter_date_range(df, start_date, end_date)
    if data.empty:
        raise ValueError("No NAV data in the given date range")

    buy_row = data.iloc[0]
    units = amount / buy_row["nav"]

    end_row = data.iloc[-1]
    final_value = units * end_row["nav"]
    days = (end_row["date"] - buy_row["date"]).days
    abs_ret = (final_value - amount) / amount * 100

    txns = pd.DataFrame([{
        "date": buy_row["date"].date(),
        "type": "BUY",
        "amount": amount,
        "nav": buy_row["nav"],
        "units": round(units, 4),
        "cumulative_units": round(units, 4),
        "cumulative_invested": amount,
    }])

    return StrategyResult(
        strategy_name="Lump Sum",
        start_date=buy_row["date"].date(),
        end_date=end_row["date"].date(),
        total_invested=amount,
        final_value=round(final_value, 2),
        total_units=round(units, 4),
        final_nav=round(end_row["nav"], 4),
        absolute_return_pct=round(abs_ret, 2),
        cagr_pct=_compute_cagr(amount, final_value, days),
        years=round(days / 365.25, 2),
        transactions=txns,
    )


# ─── 2. SIP ───────────────────────────────────────────────────────────────────

def sip(
    df: pd.DataFrame,
    monthly_amount: float,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    sip_day: int = 1,
) -> StrategyResult:
    """
    Monthly SIP: invest `monthly_amount` on the closest available NAV date
    to day `sip_day` of each month.

    Args:
        monthly_amount: ₹ to invest per month
        sip_day:        Preferred day of month (1–28; defaults to 1st)
    """
    data = _filter_date_range(df, start_date, end_date)
    if data.empty:
        raise ValueError("No NAV data in the given date range")

    data = data.set_index("date")

    # Generate monthly investment dates
    periods = pd.period_range(
        start=data.index.min().to_period("M"),
        end=data.index.max().to_period("M"),
        freq="M",
    )

    records = []
    total_units = 0.0
    total_invested = 0.0

    for period in periods:
        target_ts = pd.Timestamp(f"{period.year}-{period.month:02d}-{min(sip_day, 28):02d}")
        candidates = data[data.index >= target_ts]
        if candidates.empty:
            continue

        nav_row = candidates.iloc[0]
        units_bought = monthly_amount / nav_row["nav"]
        total_units += units_bought
        total_invested += monthly_amount

        records.append({
            "date": nav_row.name.date(),
            "type": "BUY",
            "amount": monthly_amount,
            "nav": round(nav_row["nav"], 4),
            "units": round(units_bought, 4),
            "cumulative_units": round(total_units, 4),
            "cumulative_invested": round(total_invested, 2),
        })

    if not records:
        raise ValueError("No SIP transactions could be placed in the given date range")

    txns = pd.DataFrame(records)
    final_nav = float(data.iloc[-1]["nav"])
    final_value = total_units * final_nav

    start_d = txns["date"].iloc[0]
    end_d = data.index[-1].date()
    days = (end_d - start_d).days
    abs_ret = (final_value - total_invested) / total_invested * 100

    return StrategyResult(
        strategy_name="SIP",
        start_date=start_d,
        end_date=end_d,
        total_invested=round(total_invested, 2),
        final_value=round(final_value, 2),
        total_units=round(total_units, 4),
        final_nav=round(final_nav, 4),
        absolute_return_pct=round(abs_ret, 2),
        cagr_pct=_compute_cagr(total_invested, final_value, days),
        years=round(days / 365.25, 2),
        transactions=txns,
    )


# ─── 3. Value Averaging ───────────────────────────────────────────────────────

def value_averaging(
    df: pd.DataFrame,
    monthly_target_growth: float,
    start_amount: float,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
) -> StrategyResult:
    """
    Value Averaging: each month, invest/withdraw to reach a pre-defined target value.

    Target for month N = start_amount * (1 + monthly_target_growth / 100) ^ N
    Buy more when portfolio is below target; sell/skip when above.

    Args:
        monthly_target_growth: Target monthly growth rate in % (e.g. 1.0 for 1%)
        start_amount:          Initial portfolio target for month 0
    """
    data = _filter_date_range(df, start_date, end_date)
    if data.empty:
        raise ValueError("No NAV data in the given date range")

    data = data.set_index("date")
    periods = pd.period_range(
        start=data.index.min().to_period("M"),
        end=data.index.max().to_period("M"),
        freq="M",
    )

    total_units = 0.0
    total_invested = 0.0
    records = []

    for n, period in enumerate(periods):
        target_ts = pd.Timestamp(f"{period.year}-{period.month:02d}-01")
        candidates = data[data.index >= target_ts]
        if candidates.empty:
            continue

        nav_row = candidates.iloc[0]
        current_nav = float(nav_row["nav"])
        target_value = start_amount * ((1 + monthly_target_growth / 100) ** n)
        current_value = total_units * current_nav
        invest_amount = target_value - current_value

        units_change = invest_amount / current_nav
        total_units += units_change
        total_invested += max(invest_amount, 0)   # Only count actual cash deployed

        records.append({
            "date": nav_row.name.date(),
            "type": "BUY" if invest_amount >= 0 else "SELL",
            "amount": round(invest_amount, 2),
            "nav": round(current_nav, 4),
            "units": round(units_change, 4),
            "cumulative_units": round(total_units, 4),
            "target_value": round(target_value, 2),
            "portfolio_value": round(current_value, 2),
        })

    if not records:
        raise ValueError("No VA transactions could be placed")

    txns = pd.DataFrame(records)
    final_nav = float(data.iloc[-1]["nav"])
    final_value = total_units * final_nav

    start_d = txns["date"].iloc[0]
    end_d = data.index[-1].date()
    days = (end_d - start_d).days
    abs_ret = (final_value - total_invested) / total_invested * 100 if total_invested else 0

    return StrategyResult(
        strategy_name="Value Averaging",
        start_date=start_d,
        end_date=end_d,
        total_invested=round(total_invested, 2),
        final_value=round(final_value, 2),
        total_units=round(total_units, 4),
        final_nav=round(final_nav, 4),
        absolute_return_pct=round(abs_ret, 2),
        cagr_pct=_compute_cagr(total_invested, final_value, days),
        years=round(days / 365.25, 2),
        transactions=txns,
    )


# ─── 4. Momentum (MA Crossover) ───────────────────────────────────────────────

def momentum_ma(
    df: pd.DataFrame,
    amount: float,
    fast_window: int = 50,
    slow_window: int = 200,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
) -> StrategyResult:
    """
    Momentum strategy: Lump sum deployed when fast MA crosses above slow MA (golden cross).
    Exits (sells all) when fast MA crosses below slow MA (death cross).

    Args:
        amount:       Total ₹ budget for the strategy
        fast_window:  Fast moving average days (default 50)
        slow_window:  Slow moving average days (default 200)
    """
    data = _filter_date_range(df, start_date, end_date)
    if data.empty:
        raise ValueError("No NAV data in the given date range")

    data = data.copy()
    data["ma_fast"] = data["nav"].rolling(fast_window).mean()
    data["ma_slow"] = data["nav"].rolling(slow_window).mean()
    data = data.dropna(subset=["ma_fast", "ma_slow"]).reset_index(drop=True)

    total_units = 0.0
    cash = amount
    total_invested = 0.0
    records = []
    position = False  # Are we invested?

    for _, row in data.iterrows():
        signal_buy = row["ma_fast"] > row["ma_slow"]

        if signal_buy and not position and cash > 0:
            units_bought = cash / row["nav"]
            total_units += units_bought
            total_invested += cash
            position = True
            records.append({
                "date": row["date"].date(),
                "type": "BUY",
                "nav": round(row["nav"], 4),
                "units": round(units_bought, 4),
                "amount": round(cash, 2),
                "cumulative_units": round(total_units, 4),
            })
            cash = 0.0

        elif not signal_buy and position and total_units > 0:
            sell_value = total_units * row["nav"]
            records.append({
                "date": row["date"].date(),
                "type": "SELL",
                "nav": round(row["nav"], 4),
                "units": round(total_units, 4),
                "amount": round(sell_value, 2),
                "cumulative_units": 0.0,
            })
            cash = sell_value
            total_units = 0.0
            position = False

    final_row = data.iloc[-1]
    final_nav = float(final_row["nav"])
    final_value = (total_units * final_nav) + cash

    days = (data.iloc[-1]["date"] - data.iloc[0]["date"]).days
    abs_ret = (final_value - amount) / amount * 100

    return StrategyResult(
        strategy_name=f"Momentum (MA{fast_window}/MA{slow_window})",
        start_date=data.iloc[0]["date"].date(),
        end_date=data.iloc[-1]["date"].date(),
        total_invested=round(amount, 2),
        final_value=round(final_value, 2),
        total_units=round(total_units, 4),
        final_nav=round(final_nav, 4),
        absolute_return_pct=round(abs_ret, 2),
        cagr_pct=_compute_cagr(amount, final_value, days),
        years=round(days / 365.25, 2),
        transactions=pd.DataFrame(records),
    )


# ─── 5. DCA + Stop-Loss ───────────────────────────────────────────────────────

def sip_with_stop_loss(
    df: pd.DataFrame,
    monthly_amount: float,
    stop_loss_pct: float = 20.0,
    re_entry_pct: float = 10.0,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    sip_day: int = 1,
) -> StrategyResult:
    """
    SIP with a stop-loss guard.

    - When NAV drops `stop_loss_pct`% from its peak since last entry, exit fully.
    - Re-enter when NAV recovers `re_entry_pct`% from the stop-loss exit point.
    - While stopped out, monthly installments accumulate as cash.

    Args:
        monthly_amount:  ₹ per month
        stop_loss_pct:   Drawdown from peak to trigger exit (e.g. 20 = 20%)
        re_entry_pct:    Recovery from stop-loss exit to re-enter (e.g. 10 = 10%)
    """
    data = _filter_date_range(df, start_date, end_date)
    if data.empty:
        raise ValueError("No NAV data in the given date range")

    data = data.set_index("date")
    periods = pd.period_range(
        start=data.index.min().to_period("M"),
        end=data.index.max().to_period("M"),
        freq="M",
    )

    total_units = 0.0
    total_invested = 0.0
    cash_buffer = 0.0
    peak_nav = 0.0
    stop_exit_nav: float | None = None
    stopped_out = False
    records = []

    for period in periods:
        target_ts = pd.Timestamp(f"{period.year}-{period.month:02d}-{min(sip_day, 28):02d}")
        candidates = data[data.index >= target_ts]
        if candidates.empty:
            continue

        nav_row = candidates.iloc[0]
        current_nav = float(nav_row["nav"])
        txn_date = nav_row.name.date()

        # Accumulate monthly installment
        cash_buffer += monthly_amount
        total_invested += monthly_amount

        if not stopped_out:
            peak_nav = max(peak_nav, current_nav)
            drawdown = (peak_nav - current_nav) / peak_nav * 100

            if drawdown >= stop_loss_pct and total_units > 0:
                # Trigger stop-loss: sell everything
                stop_exit_nav = current_nav
                stopped_out = True
                sell_value = total_units * current_nav
                cash_buffer += sell_value
                records.append({
                    "date": txn_date, "type": "STOP-LOSS-SELL",
                    "nav": round(current_nav, 4), "units": round(-total_units, 4),
                    "amount": round(-sell_value, 2), "cumulative_units": 0.0,
                    "note": f"Drawdown {drawdown:.1f}%",
                })
                total_units = 0.0
            else:
                # Regular SIP buy
                units_bought = cash_buffer / current_nav
                total_units += units_bought
                records.append({
                    "date": txn_date, "type": "BUY",
                    "nav": round(current_nav, 4), "units": round(units_bought, 4),
                    "amount": round(cash_buffer, 2),
                    "cumulative_units": round(total_units, 4), "note": "",
                })
                cash_buffer = 0.0
        else:
            # Waiting for re-entry signal
            assert stop_exit_nav is not None
            recovery = (current_nav - stop_exit_nav) / stop_exit_nav * 100
            if recovery >= re_entry_pct:
                units_bought = cash_buffer / current_nav
                total_units += units_bought
                stopped_out = False
                peak_nav = current_nav
                stop_exit_nav = None
                records.append({
                    "date": txn_date, "type": "RE-ENTRY",
                    "nav": round(current_nav, 4), "units": round(units_bought, 4),
                    "amount": round(cash_buffer, 2),
                    "cumulative_units": round(total_units, 4),
                    "note": f"Recovery {recovery:.1f}%",
                })
                cash_buffer = 0.0

    final_nav = float(data.iloc[-1]["nav"])
    final_value = total_units * final_nav + cash_buffer

    txns = pd.DataFrame(records)
    start_d = txns["date"].iloc[0] if not txns.empty else date.today()
    end_d = data.index[-1].date()
    days = (pd.Timestamp(end_d) - pd.Timestamp(start_d)).days
    abs_ret = (final_value - total_invested) / total_invested * 100

    return StrategyResult(
        strategy_name=f"SIP + Stop-Loss ({stop_loss_pct}%)",
        start_date=start_d,
        end_date=end_d,
        total_invested=round(total_invested, 2),
        final_value=round(final_value, 2),
        total_units=round(total_units, 4),
        final_nav=round(final_nav, 4),
        absolute_return_pct=round(abs_ret, 2),
        cagr_pct=_compute_cagr(total_invested, final_value, days),
        years=round(days / 365.25, 2),
        transactions=txns,
    )


# ─── 6. SIP + Buy on Dip ────────────────────────────────────────────────────────

def sip_buy_on_dip(
    df: pd.DataFrame,
    monthly_amount: float,
    dip_drop_pct: float = 5.0,
    subsequent_dip_drop_pct: float = 2.0,
    dip_multiplier: float = 1.0,
    cooldown_days: int = 15,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    sip_day: int = 1,
) -> StrategyResult:
    """
    Standard SIP, with additional "Buy on Dip" whenever NAV falls by 'dip_drop_pct' 
    from its highest peak. Incorporates subsequent dip triggers to average down if the
    market continues to drop.

    Args:
        monthly_amount: ₹ per month
        dip_drop_pct:   % drop from peak to trigger first dip buy
        subsequent_dip_drop_pct: % drop from the last dip buy NAV to trigger another buy
        dip_multiplier: Extra investment factor (e.g., 2.0 = double the SIP amount)
        cooldown_days:  Minimum days between two consecutive dip buys
    """
    data = _filter_date_range(df, start_date, end_date)
    if data.empty:
        raise ValueError("No NAV data in the given date range")

    total_units = 0.0
    total_invested = 0.0
    peak_nav = 0.0
    last_dip_date = pd.Timestamp("1970-01-01")
    last_dip_nav: float | None = None
    records = []

    last_sip_period = None
    
    for _, row in data.iterrows():
        current_nav = float(row["nav"])
        current_date = row["date"]
        
        current_period = current_date.to_period("M")
        is_sip_day = False
        
        if current_period != last_sip_period:
            if current_date.day >= min(sip_day, 28):
                is_sip_day = True
                
        if is_sip_day:
            units_bought = monthly_amount / current_nav
            total_units += units_bought
            total_invested += monthly_amount
            records.append({
                "date": current_date.date(), "type": "SIP-BUY",
                "nav": round(current_nav, 4), "units": round(units_bought, 4),
                "amount": round(monthly_amount, 2),
                "cumulative_units": round(total_units, 4), "note": "Regular SIP"
            })
            last_sip_period = current_period
            
        if current_nav > peak_nav:
            peak_nav = current_nav
            last_dip_nav = None  # Reset the dip buying cycle when a new all-time high is reached
        
        if peak_nav > 0:
            days_since_last_dip = (current_date - last_dip_date).days
            if days_since_last_dip >= cooldown_days:
                dip_triggered = False
                note = ""
                
                if last_dip_nav is None:
                    # Looking for the first dip from the peak
                    drawdown = (peak_nav - current_nav) / peak_nav * 100
                    if drawdown >= dip_drop_pct:
                        dip_triggered = True
                        note = f"Drop {drawdown:.1f}% from Peak"
                else:
                    # Looking for subsequent dips from the PREVIOUS dip buy point
                    drawdown = (last_dip_nav - current_nav) / last_dip_nav * 100
                    if drawdown >= subsequent_dip_drop_pct:
                        dip_triggered = True
                        note = f"Drop {drawdown:.1f}% from Prev Buy"

                if dip_triggered:
                    dip_amount = monthly_amount * dip_multiplier
                    units_bought = dip_amount / current_nav
                    total_units += units_bought
                    total_invested += dip_amount
                    records.append({
                        "date": current_date.date(), "type": "DIP-BUY",
                        "nav": round(current_nav, 4), "units": round(units_bought, 4),
                        "amount": round(dip_amount, 2),
                        "cumulative_units": round(total_units, 4),
                        "note": note
                    })
                    last_dip_date = current_date
                    last_dip_nav = current_nav

    final_nav = float(data.iloc[-1]["nav"])
    final_value = total_units * final_nav
    
    txns = pd.DataFrame(records)
    if txns.empty:
        raise ValueError("No transactions could be placed in the given date range")
        
    start_d = txns.iloc[0]["date"]
    end_d = data.iloc[-1]["date"].date()
    days = (pd.Timestamp(end_d) - pd.Timestamp(start_d)).days
    abs_ret = (final_value - total_invested) / total_invested * 100 if total_invested > 0 else 0

    return StrategyResult(
        strategy_name=f"SIP + Buy on Dip ({dip_drop_pct}%)",
        start_date=start_d,
        end_date=end_d,
        total_invested=round(total_invested, 2),
        final_value=round(final_value, 2),
        total_units=round(total_units, 4),
        final_nav=round(final_nav, 4),
        absolute_return_pct=round(abs_ret, 2),
        cagr_pct=_compute_cagr(total_invested, final_value, days),
        years=round(days / 365.25, 2),
        transactions=txns,
    )

# ─── Strategy comparison helper ───────────────────────────────────────────────

def compare_strategies(results: list[StrategyResult]) -> pd.DataFrame:
    """Return a summary DataFrame comparing multiple strategy results."""
    rows = [r.summary() for r in results]
    return pd.DataFrame(rows)
