"""Rich summary for the terminal."""

from rich.console import Console
from rich.table import Table
from rich.text import Text

from siteaudit.models import AuditResult
from siteaudit.report.summary import summarize

STYLES = {"error": "bold red", "warning": "yellow", "notice": "cyan"}


def _score_style(score: int) -> str:
    return "bold green" if score >= 90 else "bold yellow" if score >= 70 else "bold red"


def print_summary(result: AuditResult, console: Console) -> None:
    summary = summarize(result)
    header = Text.assemble(
        ("Score ", "bold"),
        (f"{summary.score}/100", _score_style(summary.score)),
        f"  ·  {summary.pages} URLs in {result.duration_s:.1f} s  ·  ",
        (f"{summary.errors} errors", STYLES["error"]),
        ", ",
        (f"{summary.warnings} warnings", STYLES["warning"]),
        ", ",
        (f"{summary.notices} notices", STYLES["notice"]),
    )
    console.print()
    console.print(f"[bold]{result.site_host}[/bold]  {result.start_url}")
    console.print(header)
    if result.limit_reached:
        console.print("[yellow]Page limit reached: raise --max-pages for a full crawl.[/yellow]")
    if not summary.groups:
        console.print("[green]No issues found.[/green]")
        return
    table = Table(show_header=True, header_style="bold", expand=False)
    table.add_column("Severity")
    table.add_column("Issue")
    table.add_column("Count", justify="right")
    table.add_column("Example")
    for group in summary.groups:
        sample = group.issues[0].url
        more = f" (+{group.count - 1})" if group.count > 1 else ""
        table.add_row(
            Text(group.severity.value, STYLES[group.severity.value]),
            group.title,
            str(group.count),
            Text(sample + more, overflow="fold"),
        )
    console.print(table)
