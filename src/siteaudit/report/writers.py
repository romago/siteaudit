"""Pick a report writer from the output file extension."""

from collections.abc import Callable
from pathlib import Path

from siteaudit.models import AuditResult
from siteaudit.report.html import render_html
from siteaudit.report.json import render_json
from siteaudit.report.markdown import render_markdown

Renderer = Callable[[AuditResult], str]

RENDERERS: dict[str, Renderer] = {
    ".html": render_html,
    ".htm": render_html,
    ".json": render_json,
    ".md": render_markdown,
    ".markdown": render_markdown,
}


def renderer_for(path: Path) -> Renderer:
    try:
        return RENDERERS[path.suffix.lower()]
    except KeyError:
        known = ", ".join(sorted(RENDERERS))
        raise ValueError(f"unknown report type {path.suffix!r} for {path}; use {known}") from None


def write_report(result: AuditResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(renderer_for(path)(result), encoding="utf-8")
