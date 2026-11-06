"""Command-line interface."""

import asyncio
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from siteaudit import USER_AGENT, __version__
from siteaudit.audit import run_audit
from siteaudit.crawler import CrawlOptions
from siteaudit.models import AuditResult, Page, Severity
from siteaudit.report.terminal import print_summary
from siteaudit.report.writers import renderer_for, write_report
from siteaudit.urls import normalize_url

app = typer.Typer(
    name="siteaudit",
    help="Crawl a website and write an SEO and technical audit report.",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode=None,
)


class FailOn(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    NEVER = "never"


EXIT_OK = 0
_DEFAULTS = CrawlOptions()
EXIT_ISSUES = 1
EXIT_USAGE = 2


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"siteaudit {__version__}")
        raise typer.Exit()


def should_fail(result: AuditResult, fail_on: FailOn) -> bool:
    if fail_on is FailOn.NEVER:
        return False
    levels = {Severity.ERROR} if fail_on is FailOn.ERROR else {Severity.ERROR, Severity.WARNING}
    return any(found.severity in levels for found in result.issues)


@app.command()
def main(
    url: Annotated[str, typer.Argument(help="Start URL, for example https://example.com")],
    report: Annotated[
        list[Path] | None,
        typer.Option(
            "--report",
            "-o",
            help="Write a report; the type follows the extension (.html, .md, .json). "
            "Repeat for several.",
        ),
    ] = None,
    max_pages: Annotated[
        int, typer.Option(min=1, help="Stop after this many URLs.")
    ] = _DEFAULTS.max_pages,
    concurrency: Annotated[
        int, typer.Option(min=1, max=20, help="Parallel requests.")
    ] = _DEFAULTS.concurrency,
    timeout: Annotated[
        float, typer.Option(min=1, help="Timeout per request, in seconds.")
    ] = _DEFAULTS.timeout,
    user_agent: Annotated[str, typer.Option(help="User-Agent header.")] = USER_AGENT,
    ignore_robots: Annotated[
        bool, typer.Option("--ignore-robots", help="Crawl URLs that robots.txt disallows.")
    ] = False,
    no_sitemap: Annotated[bool, typer.Option("--no-sitemap", help="Do not read sitemaps.")] = False,
    fail_on: Annotated[
        FailOn, typer.Option(help="Exit with code 1 when issues of this severity are found.")
    ] = FailOn.ERROR,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Print nothing but errors.")] = False,
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = None,
) -> None:
    """Crawl URL and report SEO and technical issues.

    Exit codes: 0 no issues at the --fail-on level, 1 issues found, 2 bad arguments.
    """
    console = Console(stderr=True, quiet=quiet)
    if "://" not in url:
        url = f"https://{url}"
    if normalize_url(url) is None:
        console.print(f"[red]Not an http(s) URL: {url}[/red]", soft_wrap=True)
        raise typer.Exit(EXIT_USAGE)
    reports = report or []
    try:
        for path in reports:
            renderer_for(path)
    except ValueError as exc:
        Console(stderr=True).print(f"[red]{exc}[/red]")
        raise typer.Exit(EXIT_USAGE) from None

    options = CrawlOptions(
        max_pages=max_pages,
        concurrency=concurrency,
        timeout=timeout,
        user_agent=user_agent,
        respect_robots=not ignore_robots,
        use_sitemaps=not no_sitemap,
    )
    with console.status(f"Crawling {url}") as status:
        crawled = 0

        def on_page(page: Page) -> None:
            nonlocal crawled
            crawled += 1
            status.update(f"Crawled {crawled} URLs · {page.url}")

        result = asyncio.run(run_audit(url, options, on_page))

    print_summary(result, Console(quiet=quiet))
    for path in reports:
        write_report(result, path)
        console.print(f"Report written to [bold]{path}[/bold]")
    if should_fail(result, fail_on):
        raise typer.Exit(EXIT_ISSUES)
