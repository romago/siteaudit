# siteaudit

[![CI](https://github.com/romago/siteaudit/actions/workflows/ci.yml/badge.svg)](https://github.com/romago/siteaudit/actions/workflows/ci.yml)
![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

A command-line tool that crawls a website and writes an SEO and technical audit report:
broken links with the pages that link to them, redirect chains, titles and descriptions,
canonicals, hreflang, structured data, robots.txt and the sitemap compared with what the
crawl found. The HTML report is one self-contained file you can send to a client.

```bash
pip install siteaudit
siteaudit https://example.com --max-pages 200 --report report.html
```

## Usage

```bash
siteaudit example.com                          # summary in the terminal
siteaudit https://example.com -o report.html   # HTML report
siteaudit https://example.com -o audit.md -o audit.json --fail-on warning
```

| Option | Default | |
| --- | --- | --- |
| `-o, --report PATH` | | Write a report; the type follows the extension: `.html`, `.md`, `.json`. Repeat for several. |
| `--max-pages N` | 500 | Stop after this many URLs. |
| `--concurrency N` | 5 | Parallel requests. |
| `--timeout S` | 15 | Timeout per request, in seconds. |
| `--user-agent UA` | `siteaudit/<version> (+https://github.com/romago/siteaudit)` | |
| `--ignore-robots` | off | Crawl URLs that robots.txt disallows. |
| `--no-sitemap` | off | Do not read sitemaps. |
| `--fail-on LEVEL` | `error` | `error`, `warning` or `never`. |
| `-q, --quiet` | off | Print nothing but errors. |

**Exit codes:** `0` no issues at the `--fail-on` level, `1` issues found, `2` bad arguments.
This makes it usable as a CI step after a deploy.

## How it crawls

1. Fetches the start URL. If it redirects within the same site (http to https, apex to www),
   the final host becomes the site.
2. Reads `robots.txt` and every sitemap it lists (or `/sitemap.xml`), including sitemap
   indexes and gzipped sitemaps.
3. Follows internal `<a href>` links breadth first, plus canonical and hreflang targets and
   sitemap URLs, up to `--max-pages`. `www.` and the bare domain count as one site.
4. Respects robots.txt with Google's rules: the longest matching rule wins, `*` and `$`
   wildcards work. (`urllib.robotparser` uses first-match order, which gets the default
   WordPress robots.txt wrong.)

Redirects are followed by hand, so every hop is recorded. Only HTML and XML bodies are
downloaded, up to 5 MB each. JavaScript is not executed.

## What it checks

Each check is a small function with its own test. Every issue has a code, a severity and a
short fix.

**On every HTML page**

| Code | Severity |
| --- | --- |
| `title-missing`, `title-multiple`, `title-too-long` (> 60), `title-too-short` (< 30) | error, warning, warning, notice |
| `description-missing`, `description-multiple`, `description-too-long` (> 160), `description-too-short` (< 70) | warning, warning, notice, notice |
| `h1-missing`, `h1-multiple` | warning, notice |
| `lang-missing`, `viewport-missing` | warning |
| `img-alt-missing` (an empty `alt=""` is fine) | warning |
| `noindex`, `nofollow` (meta robots or `X-Robots-Tag`) | warning, notice |
| `canonical-missing`, `canonical-multiple`, `canonical-other` | notice, warning, notice |
| `hreflang-invalid`, `hreflang-no-self` | warning |
| `json-ld-invalid` (and the `@type` values found are listed) | error |
| `slow-response` (> 1 s), `html-too-large` (> 1 MB) | warning |

**Across the site**

| Code | Severity |
| --- | --- |
| `http-4xx`, `http-5xx`, `fetch-failed`, with the pages that link to the URL | error |
| `redirect-loop`, `redirect-chain`, `link-to-redirect` | error, warning, notice |
| `title-duplicate`, `description-duplicate` | warning |
| `canonical-broken`, `canonical-redirect`, `canonical-noindex` | error, warning, error |
| `hreflang-broken`, `hreflang-not-reciprocal` | error, warning |
| `robots-missing`, `robots-no-sitemap`, `robots-blocked` | warning, notice, notice |
| `sitemap-missing`, `sitemap-invalid` | warning, error |
| `sitemap-error`, `sitemap-redirect`, `sitemap-noindex`, `sitemap-non-canonical`, `sitemap-blocked` | error, warning, error, warning, error |
| `sitemap-orphan` (only in the sitemap), `not-in-sitemap` | notice |

### Score

Each crawled URL scores by its worst issue: 1 when clean, 0.95 with only notices, 0.7 with a
warning, 0 with an error. The site score is the average times 100, minus 5 for each
site-wide error and 2 for each site-wide warning (robots.txt and sitemap files).

## Reports

- **Terminal:** score, counts and one row per issue type.
- **HTML:** one file with inline CSS, light and dark themes, filters by severity and text,
  every affected URL with details, the slowest pages, status codes, JSON-LD types and the
  full list of crawled URLs. Prints cleanly to PDF.
- **Markdown:** the same content for tickets and emails.
- **JSON:** the full result (every page and issue) plus the summary, for scripts.

## Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest --cov=siteaudit
uv run ruff check . && uv run ruff format --check .
uv run mypy
```

```
src/siteaudit/
  cli.py          Typer app: options, exit codes
  audit.py        crawl + checks -> AuditResult
  crawler.py      async crawl: robots.txt, sitemaps, link discovery, concurrency limit
  fetch.py        one request with redirect tracking, timeout and size limit
  robots.py       robots.txt with Google's matching rules
  sitemap.py      urlset, sitemap index, gzip
  parse.py        HTML -> Page
  models.py       Page, Issue, Severity, AuditResult (pydantic)
  checks/         rules.py (catalogue), page.py, site.py
  report/         summary.py, terminal.py, json.py, markdown.py, html.py + template
tests/            unit tests per module and a fake site served through respx
```

## License

MIT
