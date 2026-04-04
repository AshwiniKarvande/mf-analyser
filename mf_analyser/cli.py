"""
cli.py — Typer-based command-line interface for mf-analyser.

Usage:
    mfa --help
    mfa search "mirae"
    mfa returns 118989
    mfa returns 118989 --from-date 2019-01-01 --to-date 2024-01-01
    mfa strategy sip 118989 --amount 5000 --from-date 2019-01-01
    mfa strategy lumpsum 118989 --amount 100000 --from-date 2019-01-01
    mfa aum "Jan-Mar 2024" --scheme "PPFAS"
    mfa funds
    mfa cache list
    mfa cache clear <scheme_code>
"""

from __future__ import annotations

import logging
import re
import sys
from datetime import date
from typing import Optional

import typer
import pandas as pd
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from mf_analyser.config import DEFAULT_FUNDS, FUND_CODE_TO_NAME

app = typer.Typer(
    name="mfa",
    help="Indian Mutual Fund Analyser — fetch, cache, and analyse fund data",
    rich_markup_mode="rich",
)
strategy_app = typer.Typer(help="Run investment strategy backtests")
cache_app = typer.Typer(help="Manage local CSV cache")
app.add_typer(strategy_app, name="strategy")
app.add_typer(cache_app, name="cache")

console = Console()

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _normalize_fund_name(name: str) -> str:
    """
    Remove Plan (Direct/Regular) and Option (Growth/IDCW) from scheme names.
    This helps group sub-schemes of the same fund.
    """
    if not name:
        return ""
    # Suffixes to strip (case insensitive)
    # We strip from the last occurrence of common separators
    pats = [
        r"\s*-\s*Direct Plan.*", r"\s*-\s*Regular Plan.*",
        r"\s*-\s*DIRECT PLAN.*", r"\s*-\s*REGULAR PLAN.*",
        r"\s*-\s*Growth.*", r"\s*-\s*IDCW.*",
        r"\s*-\s*GROWTH.*", r"\s*-\s*Plan\s+Growth.*",
        r"\s*Plan\s*Growth.*", r"\s*Plan\s*IDCW.*",
        r"\s*FUND-REGULAR.*", r"\s*FUND-DIRECT.*",
        r"\s*-DIRECT\s*PLAN.*", r"\s*-REGULAR\s*PLAN.*",
        r"\s*-\s*Direct.*", r"\s*-\s*Regular.*",
        r"\s*\(\s*Direct\s*\).*", r"\s*\(\s*Regular\s*\).*",
        r"\s+Direct\s+Plan.*", r"\s+Regular\s+Plan.*",
    ]
    norm = name
    for p in pats:
        new_norm = re.sub(p, "", norm, flags=re.I).strip()
        if new_norm != norm:
            norm = new_norm
            break # Stop at the first major plan/option match
    
    # Strip trailing " Fund" if it's orphaned, for better deduplication
    norm = re.sub(r"\s+Fund$", "", norm, flags=re.I).strip()
    return norm


def _fmt_pct(v: float) -> str:
    color = "green" if v >= 0 else "red"
    return f"[{color}]{v:+.2f}%[/{color}]"


def _fmt_rs(v: float) -> str:
    return f"₹{v:,.2f}"


# ─── funds ────────────────────────────────────────────────────────────────────

@app.command("funds")
def list_default_funds():
    """List all pre-configured default funds with their scheme codes."""
    table = Table(title="Default Fund Universe", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Fund Name", style="bold cyan")
    table.add_column("Scheme Code", style="yellow")
    table.add_column("Category", style="magenta")
    table.add_column("AMC", style="green")

    for i, (name, info) in enumerate(DEFAULT_FUNDS.items(), 1):
        table.add_row(
            str(i),
            name,
            info["scheme_code"],
            info["category"],
            info["amc"],
        )
    console.print(table)
    rprint("\n[dim]Tip: Use [yellow]mfa returns <scheme_code>[/yellow] to analyse any fund.[/dim]")


# ─── search ───────────────────────────────────────────────────────────────────

@app.command("search")
def search(
    query: str = typer.Argument(..., help="Fund name substring to search"),
    top: int = typer.Option(20, "--top", "-n", help="Max results to display"),
):
    """Search for mutual fund schemes by name."""
    from mf_analyser.data.cache import search_cached_schemes

    with console.status(f"Searching for [cyan]{query!r}[/cyan]…"):
        results = search_cached_schemes(query, top_n=top)

    if results.empty:
        rprint(f"[red]No schemes found matching {query!r}[/red]")
        raise typer.Exit(1)

    table = Table(title=f"Search results for '{query}'", show_lines=True)
    table.add_column("Scheme Code", style="yellow", width=10)
    table.add_column("Scheme Name", style="cyan")

    for _, row in results.iterrows():
        table.add_row(str(row["scheme_code"]), row["scheme_name"])

    console.print(table)
    rprint(f"\n[dim]Found [bold]{len(results)}[/bold] matching schemes.[/dim]")


# ─── returns ──────────────────────────────────────────────────────────────────

@app.command("returns")
def returns_cmd(
    scheme_code: str = typer.Argument(..., help="AMFI scheme code"),
    from_date: Optional[str] = typer.Option(None, "--from-date", "-f", help="Start date YYYY-MM-DD"),
    to_date: Optional[str] = typer.Option(None, "--to-date", "-t", help="End date YYYY-MM-DD"),
    refresh: bool = typer.Option(False, "--refresh", "-r", help="Force refresh NAV cache"),
    rolling: bool = typer.Option(False, "--rolling", help="Show rolling returns summary"),
    drawdown: bool = typer.Option(False, "--drawdown", help="Show max drawdown info"),
):
    """Compute and display returns for a fund (absolute, CAGR, multi-period table)."""
    from mf_analyser.analysis.returns import (
        cagr,
        max_drawdown,
        returns_table,
        rolling_returns_summary,
    )
    from mf_analyser.data.cache import get_nav

    fund_label = FUND_CODE_TO_NAME.get(scheme_code, f"Scheme {scheme_code}")

    with console.status(f"Loading NAV for [cyan]{fund_label}[/cyan]…"):
        nav_df = get_nav(scheme_code, force_refresh=refresh)

    rprint(f"\n[bold blue]Fund:[/bold blue] {fund_label}")
    rprint(f"[dim]Records: {len(nav_df)} | From {nav_df['date'].min().date()} to {nav_df['date'].max().date()}[/dim]\n")

    # Point-to-point summary
    result = cagr(nav_df, start_date=from_date, end_date=to_date)
    rprint(f"[bold]Point-to-Point Returns[/bold]")
    rprint(f"  Period : {result['start_date']} → {result['end_date']} ({result.get('years', 'N/A')} years)")
    rprint(f"  NAV    : {_fmt_rs(result['start_nav'])} → {_fmt_rs(result['end_nav'])}")
    rprint(f"  Abs    : {_fmt_pct(result['absolute_return_pct'])}")
    rprint(f"  CAGR   : {_fmt_pct(result.get('cagr_pct', 0))}\n")

    # Multi-period table
    rprint("[bold]Trailing Returns[/bold]")
    rt = returns_table(nav_df)
    tbl = Table(show_lines=True)
    tbl.add_column("Period", style="bold")
    tbl.add_column("From", style="dim")
    tbl.add_column("Start NAV")
    tbl.add_column("End NAV")
    tbl.add_column("Absolute")
    tbl.add_column("CAGR")
    for _, row in rt.iterrows():
        tbl.add_row(
            row["period"],
            str(row["start_date"]),
            _fmt_rs(row["start_nav"]),
            _fmt_rs(row["end_nav"]),
            _fmt_pct(row["absolute_pct"]),
            _fmt_pct(row["cagr_pct"]) if not __import__("math").isnan(row["cagr_pct"]) else "–",
        )
    console.print(tbl)

    if rolling:
        rprint("\n[bold]Rolling Returns Summary[/bold]")
        for years in [1, 3, 5]:
            s = rolling_returns_summary(nav_df, years)
            rprint(
                f"  {years}Y rolling CAGR | "
                f"Min: {_fmt_pct(s['min_pct'])} | "
                f"Median: {_fmt_pct(s['median_pct'])} | "
                f"Max: {_fmt_pct(s['max_pct'])}"
            )

    if drawdown:
        dd = max_drawdown(nav_df)
        rprint(f"\n[bold]Max Drawdown[/bold]")
        rprint(f"  Peak  : {dd['peak_date']} @ {_fmt_rs(dd['peak_nav'])}")
        rprint(f"  Trough: {dd['trough_date']} @ {_fmt_rs(dd['trough_nav'])}")
        rprint(f"  Drawdown: {_fmt_pct(dd['drawdown_pct'])}")
        rprint(f"  Recovered: {dd['recovery_date'] or 'Not yet recovered'}")


# ─── strategy ─────────────────────────────────────────────────────────────────

def _print_strategy_result(result):
    from mf_analyser.analysis.strategies import StrategyResult

    s = result.summary()
    rprint(f"\n[bold green]Strategy:[/bold green] {s['strategy']}")
    rprint(f"  Period    : {s['start_date']} → {s['end_date']} ({s['years']} years)")
    rprint(f"  Invested  : {_fmt_rs(s['invested_rs'])}")
    rprint(f"  Value     : {_fmt_rs(s['final_value_rs'])}")
    rprint(f"  Gain/Loss : {_fmt_rs(s['gain_loss_rs'])}")
    rprint(f"  Abs Return: {_fmt_pct(s['absolute_return_pct'])}")
    rprint(f"  CAGR      : {_fmt_pct(s['cagr_pct'])}")
    rprint(f"  Units     : {s['total_units']:.4f} @ NAV {_fmt_rs(s['final_nav'])}")


@strategy_app.command("sip")
def strategy_sip(
    scheme_code: str = typer.Argument(..., help="AMFI scheme code"),
    amount: float = typer.Option(5000, "--amount", "-a", help="Monthly SIP amount in ₹"),
    from_date: Optional[str] = typer.Option(None, "--from-date", "-f"),
    to_date: Optional[str] = typer.Option(None, "--to-date", "-t"),
    sip_day: int = typer.Option(1, "--sip-day", help="Day of month for SIP (1–28)"),
    refresh: bool = typer.Option(False, "--refresh"),
    show_txns: bool = typer.Option(False, "--transactions", "-x", help="Show all transactions"),
):
    """Run a SIP (Systematic Investment Plan) backtest."""
    from mf_analyser.analysis.strategies import sip
    from mf_analyser.data.cache import get_nav

    nav_df = get_nav(scheme_code, force_refresh=refresh)
    result = sip(nav_df, monthly_amount=amount, start_date=from_date, end_date=to_date, sip_day=sip_day)
    _print_strategy_result(result)

    if show_txns:
        rprint("\n[bold]Transaction Log[/bold]")
        console.print(result.transactions.to_string(index=False))


@strategy_app.command("lumpsum")
def strategy_lumpsum(
    scheme_code: str = typer.Argument(..., help="AMFI scheme code"),
    amount: float = typer.Option(100000, "--amount", "-a", help="Investment amount in ₹"),
    from_date: Optional[str] = typer.Option(None, "--from-date", "-f"),
    to_date: Optional[str] = typer.Option(None, "--to-date", "-t"),
    refresh: bool = typer.Option(False, "--refresh"),
):
    """Run a lump sum investment backtest."""
    from mf_analyser.analysis.strategies import lump_sum
    from mf_analyser.data.cache import get_nav

    nav_df = get_nav(scheme_code, force_refresh=refresh)
    result = lump_sum(nav_df, amount=amount, start_date=from_date, end_date=to_date)
    _print_strategy_result(result)


@strategy_app.command("va")
def strategy_va(
    scheme_code: str = typer.Argument(..., help="AMFI scheme code"),
    start_amount: float = typer.Option(5000, "--start-amount", help="Initial month target ₹"),
    growth_rate: float = typer.Option(1.0, "--growth-rate", help="Monthly target growth % (e.g. 1.0)"),
    from_date: Optional[str] = typer.Option(None, "--from-date", "-f"),
    to_date: Optional[str] = typer.Option(None, "--to-date", "-t"),
    refresh: bool = typer.Option(False, "--refresh"),
):
    """Run a Value Averaging strategy backtest."""
    from mf_analyser.analysis.strategies import value_averaging
    from mf_analyser.data.cache import get_nav

    nav_df = get_nav(scheme_code, force_refresh=refresh)
    result = value_averaging(
        nav_df,
        monthly_target_growth=growth_rate,
        start_amount=start_amount,
        start_date=from_date,
        end_date=to_date,
    )
    _print_strategy_result(result)


@strategy_app.command("momentum")
def strategy_momentum(
    scheme_code: str = typer.Argument(..., help="AMFI scheme code"),
    amount: float = typer.Option(100000, "--amount", "-a"),
    fast: int = typer.Option(50, "--fast", help="Fast MA days"),
    slow: int = typer.Option(200, "--slow", help="Slow MA days"),
    from_date: Optional[str] = typer.Option(None, "--from-date", "-f"),
    to_date: Optional[str] = typer.Option(None, "--to-date", "-t"),
    refresh: bool = typer.Option(False, "--refresh"),
):
    """Run a Momentum (MA crossover) strategy backtest."""
    from mf_analyser.analysis.strategies import momentum_ma
    from mf_analyser.data.cache import get_nav

    nav_df = get_nav(scheme_code, force_refresh=refresh)
    result = momentum_ma(nav_df, amount=amount, fast_window=fast, slow_window=slow,
                          start_date=from_date, end_date=to_date)
    _print_strategy_result(result)


@strategy_app.command("stoploss")
def strategy_stoploss(
    scheme_code: str = typer.Argument(..., help="AMFI scheme code"),
    amount: float = typer.Option(5000, "--amount", "-a", help="Monthly SIP amount ₹"),
    stop_loss: float = typer.Option(20.0, "--stop-loss", help="Stop-loss % from peak"),
    re_entry: float = typer.Option(10.0, "--re-entry", help="Recovery % to re-enter"),
    from_date: Optional[str] = typer.Option(None, "--from-date", "-f"),
    to_date: Optional[str] = typer.Option(None, "--to-date", "-t"),
    refresh: bool = typer.Option(False, "--refresh"),
):
    """Run a SIP + Stop-Loss strategy backtest."""
    from mf_analyser.analysis.strategies import sip_with_stop_loss
    from mf_analyser.data.cache import get_nav

    nav_df = get_nav(scheme_code, force_refresh=refresh)
    result = sip_with_stop_loss(
        nav_df,
        monthly_amount=amount,
        stop_loss_pct=stop_loss,
        re_entry_pct=re_entry,
        start_date=from_date,
        end_date=to_date,
    )
    _print_strategy_result(result)


# ─── aum ──────────────────────────────────────────────────────────────────────

@app.command("aum")
def aum_cmd(
    quarter: str = typer.Argument(..., help='Quarter string e.g. "Jan-Mar 2024"'),
    scheme: Optional[str] = typer.Option(None, "--scheme", "-s", help="Filter by scheme name"),
    amc: Optional[str] = typer.Option(None, "--amc", help="Filter by AMC name"),
    top: int = typer.Option(20, "--top", "-n"),
    refresh: bool = typer.Option(False, "--refresh"),
    combine: bool = typer.Option(False, "--combine", help="Combine AUM of all variants (Direct, Regular, etc.) into 1 fund"),
):
    """Fetch and display AUM data for a quarter."""
    from mf_analyser.data.cache import get_aum

    with console.status(f"Fetching AUM for [cyan]{quarter}[/cyan]…"):
        df = get_aum(quarter, force_refresh=refresh)

    if scheme:
        col = next((c for c in df.columns if "scheme" in c.lower()), None)
        if col:
            df = df[df[col].str.contains(scheme, case=False, na=False)]

    if amc:
        col = next((c for c in df.columns if "amc" in c.lower()), None)
        if col:
            df = df[df[col].str.contains(amc, case=False, na=False)]

    if combine:
        df["fund_family"] = df["scheme_name"].apply(_normalize_fund_name)
        # Group by AMC and normalized name
        df = df.groupby(["amc", "fund_family"]).agg({
            "aum_cr": "sum",
            "scheme_code": lambda x: f"{len(x)} variants", # Just show count for codes
        }).reset_index()
        # Rename for consistency in table loop
        df.rename(columns={"fund_family": "scheme_name"}, inplace=True)
    
    # Sort by AUM (Cr) Descending before truncation
    df = df.sort_values("aum_cr", ascending=False)
    df = df.head(top)

    if df.empty:
        rprint("[red]No results matching filters.[/red]")
        raise typer.Exit(1)

    title_prefix = "Top" if not combine else "Combined Top"
    table = Table(title=f"{title_prefix} {top} AAUM Schemes: {quarter}", show_lines=True)
    table.add_column("AMC", style="green")
    table.add_column("Scheme Name", style="bold cyan")
    table.add_column("Codes" if combine else "Scheme Code", style="yellow", justify="center")
    table.add_column("AUM (Cr)", justify="right", style="magenta")

    for _, row in df.iterrows():
        table.add_row(
            str(row["amc"]),
            str(row["scheme_name"]),
            str(row["scheme_code"]),
            f"₹{row['aum_cr']:,.2f} Cr"
        )

    console.print(table)
    rprint(f"\n[dim]Showing top {len(df)} schemes by AUM for quarter: {quarter}[/dim]")


@app.command("aum-trend")
def aum_trend_cmd(
    query: str = typer.Argument(..., help="Scheme name substring to track"),
    start_year: int = typer.Option(2011, "--start", help="Start year for trend analysis"),
    end_year: Optional[int] = typer.Option(None, "--end", help="End year for trend analysis"),
    combine: bool = typer.Option(True, "--combine/--no-combine", help="Combine all fund variants into one trend"),
    refresh: bool = typer.Option(False, "--refresh", help="Force refresh AUM data"),
):
    """Display AUM growth trend and QoQ changes for a fund."""
    from mf_analyser.aum.tracker import scheme_aum_trend, aum_growth_summary

    with console.status(f"Analysing AUM trend for [cyan]{query}[/cyan]…"):
        ts = scheme_aum_trend(
            query,
            start_year=start_year,
            end_year=end_year,
            combine=combine,
            force_refresh=refresh,
        )

    if ts.empty:
        rprint(f"[red]No AUM data found for '{query}' in the selected period.[/red]")
        raise typer.Exit(1)

    # Calculate growth metrics (scheme-aware)
    ts = aum_growth_summary(ts)

    # Filter out the extra baseline quarters used for calculation
    # so we only display the range starting from start_year.
    ts["_year"] = ts["quarter"].apply(lambda q: int(q.split()[-1]))
    ts = ts[ts["_year"] >= start_year].drop(columns=["_year"])

    # Sort by quarter primarily, then by fund/scheme name
    # We do this unconditionally so multiple funds in a query result are grouped by quarter
    from mf_analyser.aum.tracker import _quarter_sort_key
    ts["_q_sort"] = ts["quarter"].map(_quarter_sort_key)
    ts = ts.sort_values(["_q_sort", "amc", "scheme_name"]).drop(columns=["_q_sort"])

    fund_name = query
    amc_name = ts["amc"].iloc[0] if "amc" in ts.columns else "Unknown AMC"

    title = f"AUM Trend: {fund_name} ({amc_name})"
    if combine:
        title += " [Combined]"
    
    table = Table(title=title, show_lines=True)
    table.add_column("Quarter", style="cyan")
    table.add_column("Fund/Scheme", style="bold white")
    if not combine:
        table.add_column("Code", style="dim yellow")
        
    table.add_column("AAUM (Cr)", justify="right", style="magenta")
    table.add_column("QoQ Change (Cr)", justify="right")
    table.add_column("QoQ %", justify="right")

    last_q = None
    for _, row in ts.iterrows():
        # Add a section separator if the quarter changes
        current_q = row.get("quarter")
        if last_q is not None and current_q != last_q:
            table.add_section()
        last_q = current_q

        change_val = row.get("aum_qoq_change_cr", 0)
        pct_val = row.get("aum_qoq_pct", 0)

        change_str = f"₹{change_val:,.2f} Cr" if pd.notnull(change_val) else "–"
        if pd.notnull(change_val):
            change_str = f"[green]+{change_str}[/green]" if change_val > 0 else f"[red]{change_str}[/red]"
        
        pct_str = _fmt_pct(pct_val) if pd.notnull(pct_val) else "–"

        row_data = [
            row["quarter"],
            row["scheme_name"],
        ]
        if not combine:
            row_data.append(str(row.get("scheme_code", "–")))
            
        row_data.extend([
            f"₹{row['aum_cr']:,.2f} Cr",
            change_str,
            pct_str
        ])
        
        table.add_row(*row_data)

    console.print(table)
    rprint(f"\n[dim]Analysis based on {len(ts)} quarters of data.[/dim]")


# ─── comparison ───────────────────────────────────────────────────────────────

@app.command("compare")
def compare_cmd(
    scheme_code: str = typer.Argument(..., help="AMFI scheme code of the target fund"),
    limit: int = typer.Option(5, "--limit", "-l", help="Number of peers to compare"),
    refresh: bool = typer.Option(False, "--refresh", "-r", help="Force refresh NAV cache"),
):
    """Compare a fund against its top category peers (Direct-Growth variants)."""
    from mf_analyser.analysis.comparison import discover_peers, compare_returns
    from mf_analyser.config import FUND_CODE_TO_NAME

    fund_label = FUND_CODE_TO_NAME.get(scheme_code, f"Scheme {scheme_code}")

    with console.status(f"Discovering peers for [cyan]{fund_label}[/cyan]…"):
        peers = discover_peers(scheme_code, limit=limit)

    peer_codes = [scheme_code] + [p[0] for p in peers]
    peer_names = {scheme_code: fund_label}
    for p_code, p_name in peers:
        peer_names[p_code] = p_name

    with console.status(f"Computing comparison for {len(peer_codes)} funds…"):
        # periods are default ["1Y", "3Y", "5Y", "10Y"]
        df = compare_returns(peer_codes)

    if df.empty:
        rprint("[red]Could not compute comparison metrics.[/red]")
        raise typer.Exit(1)

    # Add names to DF
    df["fund_name"] = df["scheme_code"].map(peer_names)

    table = Table(title=f"Peer Comparison: {fund_label}", show_lines=True)
    table.add_column("Fund Name", style="bold cyan")
    table.add_column("1Y CAGR", justify="right")
    table.add_column("3Y CAGR", justify="right")
    table.add_column("5Y CAGR", justify="right")
    table.add_column("10Y CAGR", justify="right")
    table.add_column("Max DD", justify="right", style="red")

    # Sort by 3Y CAGR descending if available, else 1Y
    sort_col = "3Y_cagr_pct" if "3Y_cagr_pct" in df.columns else "1Y_cagr_pct"
    df = df.sort_values(sort_col, ascending=False, na_position="last")

    for _, row in df.iterrows():
        display_name = row["fund_name"]
        if row["scheme_code"] == scheme_code:
            display_name = f"[bold reverse]{display_name}[/bold reverse]"

        table.add_row(
            display_name,
            _fmt_pct(row["1Y_cagr_pct"]) if pd.notnull(row["1Y_cagr_pct"]) else "–",
            _fmt_pct(row["3Y_cagr_pct"]) if pd.notnull(row["3Y_cagr_pct"]) else "–",
            _fmt_pct(row["5Y_cagr_pct"]) if pd.notnull(row["5Y_cagr_pct"]) else "–",
            _fmt_pct(row["10Y_cagr_pct"]) if pd.notnull(row.get("10Y_cagr_pct")) else "–",
            _fmt_pct(row["max_drawdown_pct"]),
        )

    console.print(table)
    rprint(f"\n[dim]* Comparisons are restricted to [bold]Direct Plan - Growth[/bold] variants.[/dim]")
    rprint(f"[dim]* Peer discovery based on category keyword search.[/dim]")


# ─── cache management ─────────────────────────────────────────────────────────

@cache_app.command("list")
def cache_list():
    """List all scheme codes with a cached NAV file."""
    from mf_analyser.data.cache import list_cached_navs

    codes = list_cached_navs()
    if not codes:
        rprint("[yellow]No cached NAV data found.[/yellow]")
        return

    table = Table(title="Cached NAV Files", show_lines=True)
    table.add_column("Scheme Code", style="yellow")
    table.add_column("Fund Name", style="cyan")

    for code in sorted(codes):
        name = FUND_CODE_TO_NAME.get(code, "–")
        table.add_row(code, name)

    console.print(table)
    rprint(f"\n[dim]Total cached schemes: {len(codes)}[/dim]")


# ─── Holdings analysis ────────────────────────────────────────────────────────

@app.command("holdings")
def holdings_cmd(
    query: str = typer.Argument(..., help="Scheme code or name"),
    refresh: bool = typer.Option(False, "--refresh", help="Force refresh holdings from Groww"),
    slug: Optional[str] = typer.Option(None, "--slug", help="Custom Groww slug if mapping is missing"),
):
    """
    Display current portfolio holdings and sector allocation.
    """
    from mf_analyser.data.cache import get_holdings, search_cached_schemes
    from mf_analyser.analysis.holdings import get_top_holdings, get_sector_allocation

    # Resolve scheme code
    scheme_code = query
    if not query.isdigit():
        results = search_cached_schemes(query, top_n=1)
        if results.empty:
            rprint(f"[red]No scheme found matching '{query}'.[/red]")
            raise typer.Exit(1)
        scheme_code = results.iloc[0]["scheme_code"]
    
    fund_name = FUND_CODE_TO_NAME.get(scheme_code, f"Scheme {scheme_code}")

    try:
        data = get_holdings(scheme_code, force_refresh=refresh, slug=slug)
    except Exception as e:
        rprint(f"[red]Error fetching holdings: {str(e)}[/red]")
        if "No Groww slug mapping" in str(e):
            rprint("\n[yellow]Tip: Use --slug to provide the Groww URL slug for this fund.[/yellow]")
        raise typer.Exit(1)

    rprint(f"\n[bold cyan]{fund_name}[/bold cyan]")
    rprint(f"[dim]As of: {data.get('as_of_date', 'Unknown')} | Total Holdings: {data['total_holdings']}[/dim]\n")

    # Top Holdings Table
    top_h = get_top_holdings(data, top_n=15)
    h_table = Table(title="Top 15 Holdings", show_lines=True)
    h_table.add_column("Stock/Instrument", style="bold white")
    h_table.add_column("Sector", style="dim")
    h_table.add_column("Weight (%)", justify="right", style="green")

    for h in top_h:
        h_table.add_row(
            h["name"],
            h["sector"],
            f"{h['weightage']:.2f}%"
        )
    console.print(h_table)

    # Sector Allocation Table
    sector_df = get_sector_allocation(data)
    s_table = Table(title="Sector Allocation", show_lines=True)
    s_table.add_column("Sector", style="magenta")
    s_table.add_column("Allocation (%)", justify="right")

    for _, row in sector_df.iterrows():
        s_table.add_row(row["sector"], f"{row['weightage']:.2f}%")
    console.print(s_table)


@app.command("holdings-diff")
def holdings_diff_cmd(
    query: str = typer.Argument(..., help="Scheme code or name"),
):
    """
    Shows changes in holdings compared to the previous cached snapshot.
    Note: Requires at least two cached snapshots for this scheme.
    """
    import json
    from mf_analyser.data.cache import search_cached_schemes
    from mf_analyser.analysis.holdings import get_snapshot_history, analyze_changes

    scheme_code = query
    if not query.isdigit():
        results = search_cached_schemes(query, top_n=1)
        if results.empty:
            rprint(f"[red]No scheme found matching '{query}'.[/red]")
            raise typer.Exit(1)
        scheme_code = results.iloc[0]["scheme_code"]

    history = get_snapshot_history(scheme_code)
    if len(history) < 2:
        rprint(f"[yellow]Need at least 2 historical snapshots for comparison. Currently have {len(history)}.[/yellow]")
        rprint("[dim]Historical snapshots are created automatically every time you run 'mfa holdings --refresh' on a new month.[/dim]")
        return

    # Load latest and second-latest
    with open(history[-1], "r") as f:
        new_data = json.load(f)
    with open(history[-2], "r") as f:
        old_data = json.load(f)

    rprint(f"\n[bold cyan]Portfolio Changes for {FUND_CODE_TO_NAME.get(scheme_code, scheme_code)}[/bold cyan]")
    rprint(f"[dim]Comparing {old_data.get('as_of_date', 'Past')} vs {new_data.get('as_of_date', 'Latest')}[/dim]\n")

    changes = analyze_changes(old_data, new_data)

    # Added Table
    if changes["added"]:
        added_t = Table(title="New Additions", show_lines=False, border_style="green")
        added_t.add_column("Stock", style="green")
        added_t.add_column("Weight", justify="right")
        for item in changes["added"]:
            added_t.add_row(item["name"], f"{item['weight']:.2f}%")
        console.print(added_t)

    # Exited Table
    if changes["exited"]:
        exited_t = Table(title="Fully Exited", show_lines=False, border_style="red")
        exited_t.add_column("Stock", style="red")
        exited_t.add_column("Former Weight", justify="right")
        for item in changes["exited"]:
            exited_t.add_row(item["name"], f"{item['weight']:.2f}%")
        console.print(exited_t)

    # Increased/Decreased
    if changes["increased"] or changes["decreased"]:
        shift_t = Table(title="Significant Weightage Shifts (>0.01%)", show_lines=True)
        shift_t.add_column("Stock")
        shift_t.add_column("Change", justify="right")
        shift_t.add_column("New Weight", justify="right")

        for item in changes["increased"][:10]: # Top 10 increases
            shift_t.add_row(item["name"], f"[green]+{item['diff']:.2f}%[/green]", f"{item['new_weight']:.2f}%")
        
        if changes["increased"] and changes["decreased"]:
            shift_t.add_section()

        for item in changes["decreased"][:10]: # Top 10 decreases
            shift_t.add_row(item["name"], f"[red]{item['diff']:.2f}%[/red]", f"{item['new_weight']:.2f}%")
        
        console.print(shift_t)


@cache_app.command("clear")
def cache_clear(
    scheme_code: Optional[str] = typer.Argument(None, help="Scheme code to clear (omit to clear all)"),
    all_: bool = typer.Option(False, "--all", help="Clear all cached NAV files"),
):
    """Clear cached NAV CSV file(s)."""
    from mf_analyser.data.cache import clear_nav_cache, list_cached_navs

    if all_:
        codes = list_cached_navs()
        for code in codes:
            clear_nav_cache(code)
        rprint(f"[green]Cleared {len(codes)} cached NAV files.[/green]")
    elif scheme_code:
        clear_nav_cache(scheme_code)
        rprint(f"[green]Cleared cache for scheme {scheme_code}.[/green]")
    else:
        rprint("[red]Specify a scheme code or use --all.[/red]")
        raise typer.Exit(1)


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
