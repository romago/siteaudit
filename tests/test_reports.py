import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from rich.console import Console

from siteaudit.checks.rules import issue
from siteaudit.models import AuditResult, Issue, JsonLd, Page
from siteaudit.report.html import render_html
from siteaudit.report.json import render_json
from siteaudit.report.markdown import render_markdown
from siteaudit.report.summary import group_issues, score, summarize
from siteaudit.report.terminal import print_summary
from siteaudit.report.writers import renderer_for, write_report

B = "https://example.com"


def page(path: str, **fields: object) -> Page:
    defaults: dict[str, object] = {"status": 200, "content_type": "text/html", "response_ms": 120}
    return Page(url=B + path, final_url=B + path, **(defaults | fields))


def result_with(pages: list[Page], issues: list[Issue]) -> AuditResult:
    return AuditResult(
        start_url=f"{B}/",
        site_host="example.com",
        started_at=datetime(2026, 11, 6, 12, 0, tzinfo=UTC),
        duration_s=3.2,
        pages=pages,
        issues=issues,
        robots_url=f"{B}/robots.txt",
        robots_status=200,
    )


@pytest.fixture
def result() -> AuditResult:
    pages = [
        page(
            "/",
            title="Home <script>alert(1)</script>",
            json_ld=[JsonLd(valid=True, types=["WebSite"])],
        ),
        page("/about", title="About", response_ms=1500),
        page("/missing", status=404),
        page("/clean"),
    ]
    issues = [
        issue("http-4xx", f"{B}/missing", "HTTP 404. Linked from 1 page.", [f"{B}/about"]),
        issue("title-too-short", f"{B}/about", "5 characters: About"),
        issue("slow-response", f"{B}/about", "Server responded in 1500 ms."),
        issue("canonical-missing", f"{B}/", "No canonical link."),
    ]
    return result_with(pages, issues)


def test_score(result: AuditResult) -> None:
    # pages: notice 0.95, warning 0.7, error 0, clean 1 -> 2.65 / 4
    assert score(result) == 66
    assert score(result_with([page("/")], [])) == 100
    assert score(result_with([], [])) == 0
    site_wide = [issue("robots-missing", f"{B}/robots.txt", "robots.txt returned HTTP 404.")]
    assert score(result_with([page("/")], site_wide)) == 98


def test_group_issues_orders_by_severity_then_count(result: AuditResult) -> None:
    groups = group_issues(result.issues)
    assert [g.code for g in groups] == [
        "http-4xx",
        "slow-response",
        "canonical-missing",
        "title-too-short",
    ]
    assert groups[0].fix.startswith("Restore the page")


def test_summary(result: AuditResult) -> None:
    summary = summarize(result)
    assert (summary.errors, summary.warnings, summary.notices) == (1, 1, 2)
    assert summary.status_counts == {"2xx": 3, "4xx": 1}
    assert summary.slowest[0].url == f"{B}/about"
    assert summary.json_ld_types == {"WebSite": 1}


def test_json(result: AuditResult) -> None:
    data = json.loads(render_json(result))
    assert data["summary"]["score"] == 66
    assert data["rules"]["http-4xx"]["count"] == 1
    assert data["issues"][0]["related"] == [f"{B}/about"]
    assert data["pages"][0]["title"].startswith("Home")
    assert AuditResult.model_validate(data).issues == result.issues


def test_markdown(result: AuditResult) -> None:
    text = render_markdown(result)
    assert text.startswith("# Site audit: example.com")
    assert "**Score: 66/100**" in text
    assert "| 🔴 error | Broken page or link (4xx) | 1 |" in text
    assert f"- <{B}/missing> — HTTP 404. Linked from 1 page.\n  - {B}/about" in text
    assert "## Slowest pages" in text


def test_html_is_self_contained_and_escaped(result: AuditResult) -> None:
    text = render_html(result)
    assert text.startswith("<!doctype html>")
    assert "<title>Site audit: example.com</title>" in text
    assert "Home &lt;script&gt;alert(1)&lt;/script&gt;" in text
    assert "<script>alert(1)</script>" not in text
    assert 'id="http-4xx"' in text
    assert "--score: 66" in text
    # nothing is loaded from elsewhere
    assert "<link rel=" not in text
    assert "src=" not in text


def test_html_without_issues() -> None:
    assert "No issues found." in render_html(result_with([page("/")], []))


def test_terminal(result: AuditResult) -> None:
    console = Console(record=True, width=120)
    print_summary(result, console)
    out = console.export_text()
    assert "Score 66/100" in out
    assert "Broken page or link (4xx)" in out


def test_writers(result: AuditResult, tmp_path: Path) -> None:
    for name in ("r.html", "r.md", "sub/r.json"):
        write_report(result, tmp_path / name)
        assert (tmp_path / name).stat().st_size > 0
    with pytest.raises(ValueError, match="unknown report type"):
        renderer_for(Path("r.pdf"))
