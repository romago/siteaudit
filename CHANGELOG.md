# Changelog

## 0.1.0 — 2026-11-06

First release, published on PyPI as `site-audit` (the command is `siteaudit`).

- Async crawl of one site: robots.txt (Google's matching rules), sitemaps and sitemap
  indexes (gzip too), internal links, canonical and hreflang targets; concurrency and
  page limits; every redirect hop recorded.
- 11 per-page checks: title, meta description, h1, lang, viewport, image alt,
  noindex/nofollow, canonical, hreflang codes, JSON-LD syntax, response time and HTML size.
- 9 site-wide checks: broken links with the pages that link to them, redirect chains and
  loops, duplicate titles and descriptions, canonical and hreflang targets, robots.txt,
  sitemap files, and the sitemap compared with the crawl.
- Reports: terminal summary, JSON, Markdown and a self-contained HTML file with a score.
- Exit code 1 when issues of the `--fail-on` level are found, for use in CI.
