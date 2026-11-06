# siteaudit

[![CI](https://github.com/romago/siteaudit/actions/workflows/ci.yml/badge.svg)](https://github.com/romago/siteaudit/actions/workflows/ci.yml)

A command-line tool that crawls a website and writes an SEO and technical audit report.

> Work in progress. v0.1 is under development.

## Usage

```bash
pip install siteaudit
siteaudit https://example.com --max-pages 200 --report report.html
```

## Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy
```

## License

MIT
