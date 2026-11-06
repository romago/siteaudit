"""Numbers and groupings shared by every report format."""

from collections import Counter

from pydantic import BaseModel, Field

from siteaudit.checks.rules import RULES
from siteaudit.models import AuditResult, Issue, Page, Severity

# How much a page's worst issue costs it, and what a site-wide issue costs the site.
PAGE_PENALTY = {Severity.ERROR: 1.0, Severity.WARNING: 0.3, Severity.NOTICE: 0.05}
SITE_PENALTY = {Severity.ERROR: 5.0, Severity.WARNING: 2.0, Severity.NOTICE: 0.0}


class IssueGroup(BaseModel):
    code: str
    severity: Severity
    title: str
    fix: str
    issues: list[Issue] = Field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.issues)


class Summary(BaseModel):
    score: int
    pages: int
    html_pages: int
    errors: int
    warnings: int
    notices: int
    groups: list[IssueGroup]
    status_counts: dict[str, int]
    avg_response_ms: float
    slowest: list[Page]
    json_ld_types: dict[str, int]


def score(result: AuditResult) -> int:
    """Site score from 0 to 100.

    A page with an error scores 0, with a warning 0.7, with only notices 0.95, and a
    clean page 1. The site score is the average, minus 5 per site-wide error and 2 per
    site-wide warning (robots.txt, sitemap files).
    """
    if not result.pages:
        return 0
    worst: dict[str, Severity] = {}
    page_urls = {page.url for page in result.pages}
    site_penalty = 0.0
    for found in result.issues:
        if found.url in page_urls:
            current = worst.get(found.url)
            if current is None or found.severity.rank < current.rank:
                worst[found.url] = found.severity
        else:
            site_penalty += SITE_PENALTY[found.severity]
    total = sum(1 - PAGE_PENALTY[worst[p.url]] if p.url in worst else 1 for p in result.pages)
    value = 100 * total / len(result.pages) - site_penalty
    return max(0, min(100, round(value)))


def group_issues(issues: list[Issue]) -> list[IssueGroup]:
    groups: dict[str, IssueGroup] = {}
    for found in issues:
        group = groups.get(found.code)
        if group is None:
            rule = RULES[found.code]
            group = groups[found.code] = IssueGroup(
                code=rule.code, severity=rule.severity, title=rule.title, fix=rule.fix
            )
        group.issues.append(found)
    return sorted(groups.values(), key=lambda g: (g.severity.rank, -g.count, g.code))


def summarize(result: AuditResult, slowest: int = 10) -> Summary:
    counts = Counter(found.severity for found in result.issues)
    statuses: Counter[str] = Counter()
    for page in result.pages:
        if page.error:
            statuses["failed"] += 1
        elif page.redirects:
            statuses["3xx"] += 1
        elif page.status is not None:
            statuses[f"{page.status // 100}xx"] += 1
    served = [p for p in result.pages if p.status is not None and not p.redirects]
    types: Counter[str] = Counter()
    for page in result.pages:
        for kind in {t for block in page.json_ld for t in block.types}:
            types[kind] += 1
    html = [p for p in result.pages if p.is_indexable_html]
    return Summary(
        score=score(result),
        pages=len(result.pages),
        html_pages=len(html),
        errors=counts[Severity.ERROR],
        warnings=counts[Severity.WARNING],
        notices=counts[Severity.NOTICE],
        groups=group_issues(result.issues),
        status_counts=dict(sorted(statuses.items())),
        avg_response_ms=round(sum(p.response_ms for p in served) / len(served), 1) if served else 0,
        slowest=sorted(html, key=lambda p: p.response_ms, reverse=True)[:slowest],
        json_ld_types=dict(types.most_common()),
    )
