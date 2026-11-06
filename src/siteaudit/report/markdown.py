"""Markdown report, for pasting into a ticket, an email or a README."""

from siteaudit.models import AuditResult
from siteaudit.report.summary import summarize

MAX_URLS_PER_GROUP = 50
ICONS = {"error": "🔴", "warning": "🟠", "notice": "🔵"}


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render_markdown(result: AuditResult) -> str:
    summary = summarize(result)
    lines = [
        f"# Site audit: {result.site_host}",
        "",
        f"Start URL: {result.start_url}  ",
        f"Date: {result.started_at:%Y-%m-%d %H:%M} UTC, {result.duration_s:.0f} s  ",
        f"Pages crawled: {summary.pages}"
        + (" (page limit reached)" if result.limit_reached else ""),
        "",
        f"**Score: {summary.score}/100** · {summary.errors} errors · "
        f"{summary.warnings} warnings · {summary.notices} notices",
        "",
    ]
    if summary.groups:
        lines += ["| Severity | Issue | Count |", "| --- | --- | ---: |"]
        for group in summary.groups:
            icon = ICONS[group.severity.value]
            lines.append(
                f"| {icon} {group.severity.value} | {_cell(group.title)} | {group.count} |"
            )
        lines.append("")
    else:
        lines += ["No issues found.", ""]

    for group in summary.groups:
        lines += [
            f"## {ICONS[group.severity.value]} {group.title} ({group.count})",
            "",
            f"`{group.code}` · {group.fix}",
            "",
        ]
        for found in group.issues[:MAX_URLS_PER_GROUP]:
            lines.append(f"- <{found.url}> — {found.message}")
            for related in found.related[:10]:
                lines.append(f"  - {related}")
            if len(found.related) > 10:
                lines.append(f"  - and {len(found.related) - 10} more")
        if group.count > MAX_URLS_PER_GROUP:
            lines.append(f"- and {group.count - MAX_URLS_PER_GROUP} more")
        lines.append("")

    if summary.slowest:
        lines += [
            "## Slowest pages",
            "",
            "| URL | Response, ms | Size, KB |",
            "| --- | ---: | ---: |",
        ]
        for page in summary.slowest:
            lines.append(f"| {page.url} | {page.response_ms:.0f} | {page.size / 1024:.0f} |")
        lines.append("")
    return "\n".join(lines)
