"""Command-line interface."""

from typing import Annotated

import typer

from siteaudit import __version__

app = typer.Typer(
    name="siteaudit",
    help="Crawl a website and write an SEO and technical audit report.",
    add_completion=False,
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"siteaudit {__version__}")
        raise typer.Exit()


@app.command()
def main(
    url: Annotated[str, typer.Argument(help="Start URL, for example https://example.com")],
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
    """Audit URL."""
    typer.echo(f"Auditing {url} (not implemented yet)")
