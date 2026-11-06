"""Self-contained HTML report: one file with inline CSS and a few lines of JS."""

from collections import Counter

from jinja2 import Environment, PackageLoader, select_autoescape

from siteaudit import __version__
from siteaudit.models import AuditResult
from siteaudit.report.summary import summarize

_env = Environment(
    loader=PackageLoader("siteaudit", "report/templates"),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_html(result: AuditResult) -> str:
    summary = summarize(result)
    issues_per_url = Counter(found.url for found in result.issues)
    template = _env.get_template("report.html")
    return template.render(
        result=result,
        summary=summary,
        issues_per_url=issues_per_url,
        version=__version__,
    )
