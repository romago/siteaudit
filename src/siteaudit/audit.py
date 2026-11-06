"""Run a crawl and every check, and collect the result."""

import time
from collections.abc import Callable
from datetime import UTC, datetime

from siteaudit.checks.page import run_page_checks
from siteaudit.checks.site import run_site_checks
from siteaudit.crawler import CrawlOptions, CrawlResult, crawl
from siteaudit.models import AuditResult, Issue, Page


def collect_issues(result: CrawlResult) -> list[Issue]:
    issues = [found for page in result.pages.values() for found in run_page_checks(page)]
    issues += run_site_checks(result)
    issues.sort(key=lambda i: (i.severity.rank, i.code, i.url))
    return issues


def build_result(result: CrawlResult, started_at: datetime, duration_s: float) -> AuditResult:
    return AuditResult(
        start_url=result.start_url,
        site_host=result.site_host,
        started_at=started_at,
        duration_s=round(duration_s, 2),
        pages=list(result.pages.values()),
        issues=collect_issues(result),
        sitemap_urls=result.sitemap_urls,
        robots_url=result.robots_url,
        robots_status=result.robots_status,
        limit_reached=result.limit_reached,
    )


async def run_audit(
    url: str,
    options: CrawlOptions | None = None,
    on_page: Callable[[Page], None] | None = None,
) -> AuditResult:
    started_at = datetime.now(UTC)
    clock = time.perf_counter()
    result = await crawl(url, options, on_page)
    return build_result(result, started_at, time.perf_counter() - clock)
