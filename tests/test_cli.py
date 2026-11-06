import json
from pathlib import Path

from typer.testing import CliRunner

from siteaudit import __version__
from siteaudit.cli import app
from tests.conftest import FakeSite

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == f"siteaudit {__version__}"


def test_audit_writes_reports_and_fails_on_errors(site: FakeSite, tmp_path: Path) -> None:
    html, md, js = tmp_path / "r.html", tmp_path / "r.md", tmp_path / "r.json"
    result = runner.invoke(
        app,
        ["example.com", "-o", str(html), "-o", str(md), "--report", str(js), "--concurrency", "2"],
    )
    assert result.exit_code == 1, result.output
    assert "Score" in result.stdout
    assert html.read_text().startswith("<!doctype html>")
    assert md.read_text().startswith("# Site audit: example.com")
    data = json.loads(js.read_text())
    assert data["start_url"] == "https://example.com/"
    assert data["summary"]["errors"] > 0


def test_fail_on_never(site: FakeSite) -> None:
    assert runner.invoke(app, ["https://example.com", "--fail-on", "never", "-q"]).exit_code == 0


def test_clean_site_exits_zero(site: FakeSite) -> None:
    site.add("/robots.txt", body="User-agent: *\nDisallow:\n", content_type="text/plain")
    site.add("/sitemap.xml", status=404, body="none")
    good = (
        '<html lang="en"><head><meta name="viewport" content="width=device-width">'
        "<title>A good page title that is long enough</title>"
        '<meta name="description" content="' + "d" * 100 + '">'
        '<link rel="canonical" href="https://example.com/"></head><body><h1>Hi</h1></body></html>'
    )
    site.add("/", body=good)
    result = runner.invoke(app, ["https://example.com/", "--fail-on", "error"])
    assert result.exit_code == 0, result.output


def test_bad_arguments() -> None:
    assert runner.invoke(app, ["ftp://example.com"]).exit_code == 2
    assert runner.invoke(app, ["https://example.com", "-o", "report.pdf"]).exit_code == 2
    assert runner.invoke(app, ["https://example.com", "--max-pages", "0"]).exit_code == 2
