"""JSON report: the full result plus the summary numbers and the rules that fired."""

import json
from typing import Any

from siteaudit import __version__
from siteaudit.models import AuditResult
from siteaudit.report.summary import summarize


def render_json(result: AuditResult) -> str:
    summary = summarize(result)
    data: dict[str, Any] = {
        "tool": {"name": "siteaudit", "version": __version__},
        "summary": {
            "score": summary.score,
            "pages": summary.pages,
            "html_pages": summary.html_pages,
            "errors": summary.errors,
            "warnings": summary.warnings,
            "notices": summary.notices,
            "status_counts": summary.status_counts,
            "avg_response_ms": summary.avg_response_ms,
            "json_ld_types": summary.json_ld_types,
        },
        "rules": {
            group.code: {
                "severity": group.severity,
                "title": group.title,
                "fix": group.fix,
                "count": group.count,
            }
            for group in summary.groups
        },
        **result.model_dump(mode="json"),
    }
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
