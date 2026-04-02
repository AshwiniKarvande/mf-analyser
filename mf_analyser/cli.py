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
import sys
from datetime import date
from typing import Optional

import typer
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

    df = df.head(top)
    if df.empty:
        rprint("[red]No results matching filters.[/red]")
        raise typer.Exit(1)

    console.print(df.to_string(index=False))
    rprint(f"\n[dim]Showing {len(df)} rows for quarter: {quarter}[/dim]")


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
