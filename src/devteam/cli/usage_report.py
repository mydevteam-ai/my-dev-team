"""Rendering for `devteam --usage-report`: rich tables over the run log's pure rollup."""
from rich import box
from rich import print  # pylint: disable=redefined-builtin
from rich.panel import Panel
from rich.table import Table
from devteam.utils.cost_optimization import _KIND_STYLES
from devteam.utils.run_log import RunLog, default_run_log_path
from devteam.utils.usage_stats import filter_since, rollup_usage

PANEL_WIDTH = 75


def _format_duration(seconds: float) -> str:
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _totals_panel(stats: dict) -> Panel:
    overall = stats['overall']
    table = Table(show_header=False, box=None, expand=True)
    table.add_column("Metric", style='cyan', no_wrap=True)
    table.add_column("Value", justify='right', style='yellow')
    table.add_row("Runs:", str(stats['runs']))
    table.add_row("LLM Calls:", str(overall['calls']))
    table.add_row("Repaired Calls:", f"{overall['repaired']} ({stats['repair_rate']:.0%})")
    table.add_row("Prompt Tokens:", f"{overall['input_tokens']:,}")
    table.add_row("Cached Tokens:", f"{overall['cached_tokens']:,} ({stats['cache_hit_rate']:.0%} hit rate)")
    table.add_row("Completion Tokens:", f"{overall['output_tokens']:,}")
    table.add_row("Total Tokens:", f"{overall['total_tokens']:,}")
    table.add_row("Wall-clock Time:", _format_duration(stats['duration']['total_s']))
    table.add_row("", "")
    table.add_row("[bold white]Estimated Cost:[/bold white]", f"[bold green]${overall['cost']:.4f}[/bold green]")
    return Panel(table, title="[bold white]📊 USAGE TOTALS[/bold white]",
                 border_style='blue', width=PANEL_WIDTH, padding=(1, 3))


def _bucket_table(title: str, key_header: str, buckets: list[dict], run_level: bool) -> Panel:
    table = Table(show_edge=False, box=box.SIMPLE, expand=True)
    table.add_column(key_header, style='cyan')
    table.add_column("Runs" if run_level else "Calls", justify='right')
    table.add_column("Tokens", justify='right')
    table.add_column("Cost", justify='right', style='green')
    if not run_level:
        table.add_column("Repaired", justify='right')
    for bucket in buckets:
        row = [
            str(bucket['key']),
            str(bucket['runs'] if run_level else bucket['calls']),
            f"{bucket['total_tokens']:,}",
            f"${bucket['cost']:.4f}",
        ]
        if not run_level:
            row.append(str(bucket['repaired']))
        table.add_row(*row)
    return Panel(table, title=f"[bold white]{title}[/bold white]",
                 border_style='blue', width=PANEL_WIDTH, padding=(0, 1))


def _trends_panel(stats: dict) -> Panel:
    trends = stats['trends']
    if not trends:
        return Panel(
            "[bold green]✅ No recurring diagnostics across the logged runs.[/bold green]",
            title="[bold green]🔍 CROSS-RUN TRENDS[/bold green]",
            border_style='green', width=PANEL_WIDTH, padding=(1, 3))
    table = Table(show_edge=False, show_lines=True, box=box.SIMPLE, expand=True)
    table.add_column("Issue Type", justify='left')
    table.add_column("Agent", justify='center')
    table.add_column("Runs Affected", justify='right')
    for trend in trends:
        style, label = _KIND_STYLES.get(trend['kind'], ('white', trend['kind']))
        table.add_row(f"[{style}]{label}[/{style}]", f"[cyan]{trend['agent']}[/cyan]",
                      f"{trend['runs_affected']} of {trend['total_runs']}")
    return Panel(table, title="[bold red]🔍 CROSS-RUN TRENDS[/bold red]",
                 border_style='red', width=PANEL_WIDTH, padding=(0, 1))


def show_usage_report(since_days: int | None = None) -> None:
    records = RunLog().read_records()
    if since_days:
        records = filter_since(records, since_days)
    if not records:
        scope = f"the last {since_days} day(s) of " if since_days else ""
        print(f"No run records found in {scope}{default_run_log_path()}.")
        print("Records are appended after every run unless 'run_log: false' is set in config.yaml.")
        return
    stats = rollup_usage(records)
    print()
    print(_totals_panel(stats))
    print(_bucket_table("BY OUTCOME", "Outcome", stats['outcomes'], run_level=True))
    print(_bucket_table("BY AGENT", "Agent", stats['by_agent'], run_level=False))
    print(_bucket_table("BY MODEL", "Model", stats['by_model'], run_level=False))
    print(_bucket_table("BY PROVIDER", "Provider", stats['by_provider'], run_level=True))
    print(_bucket_table("BY WORKFLOW", "Workflow", stats['by_workflow'], run_level=True))
    print(_bucket_table("BY DAY", "Day", stats['by_day'], run_level=True))
    print(_trends_panel(stats))
    print()
