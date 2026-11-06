from typer.testing import CliRunner

from siteaudit import __version__
from siteaudit.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == f"siteaudit {__version__}"
