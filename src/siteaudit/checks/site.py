"""Cross-page checks that need the whole crawl: links, redirects, duplicates, sitemaps."""

from collections import defaultdict
from collections.abc import Callable, Iterator

from siteaudit.checks.rules import issue
from siteaudit.crawler import CrawlResult
from siteaudit.models import Issue, Page
from siteaudit.urls import is_internal

SiteCheck = Callable[[CrawlResult], Iterator[Issue]]
SITE_CHECKS: list[SiteCheck] = []

SITEMAP_REFERRER = "sitemap.xml"


def site_check(func: SiteCheck) -> SiteCheck:
    SITE_CHECKS.append(func)
    return func


def run_site_checks(crawl: CrawlResult) -> list[Issue]:
    return [found for check in SITE_CHECKS for found in check(crawl)]


def _reached_by_links(crawl: CrawlResult) -> set[str]:
    """URLs that some crawled page links to, directly or through a redirect."""
    reached = {url for url, sources in crawl.inlinks.items() if sources}
    for page in crawl.pages.values():
        if page.redirects and page.url in reached:
            reached.add(page.final_url)
    return reached


def _referrers(crawl: CrawlResult, url: str) -> list[str]:
    return sorted(crawl.inlinks.get(url, ()))


def _linked_from(referrers: list[str]) -> str:
    if not referrers:
        return ""
    return f" Linked from {len(referrers)} page{'s' if len(referrers) != 1 else ''}."


def _is_canonical_self(page: Page) -> bool:
    return page.canonical is None or page.canonical == page.url


def _indexable(page: Page) -> bool:
    """A page that should be in search: 2xx HTML, not noindex, canonical to itself."""
    return page.is_indexable_html and not page.noindex and _is_canonical_self(page)


def _describe_failure(page: Page) -> str:
    return page.error or f"HTTP {page.status}"


@site_check
def check_status(crawl: CrawlResult) -> Iterator[Issue]:
    """4xx, 5xx and failed requests, with the internal pages that link to them."""
    for page in crawl.pages.values():
        referrers = _referrers(crawl, page.url)
        suffix = _linked_from(referrers)
        if page.error == "redirect loop":
            hops = [hop.url for hop in page.redirects]
            yield issue("redirect-loop", page.url, f"Redirects in a loop.{suffix}", hops)
        elif page.error:
            yield issue("fetch-failed", page.url, f"{page.error}.{suffix}", referrers)
        elif page.status is not None and 400 <= page.status < 500:
            yield issue("http-4xx", page.url, f"HTTP {page.status}.{suffix}", referrers)
        elif page.status is not None and page.status >= 500:
            yield issue("http-5xx", page.url, f"HTTP {page.status}.{suffix}", referrers)


@site_check
def check_redirects(crawl: CrawlResult) -> Iterator[Issue]:
    for page in crawl.pages.values():
        if not page.redirects or page.error:
            continue
        chain = [hop.url for hop in page.redirects] + [page.final_url]
        if len(page.redirects) > 1:
            statuses = " -> ".join(str(hop.status) for hop in page.redirects)
            yield issue(
                "redirect-chain",
                page.url,
                f"{len(page.redirects)} redirects ({statuses}) before {page.final_url}.",
                chain,
            )
        referrers = _referrers(crawl, page.url)
        if referrers:
            yield issue(
                "link-to-redirect",
                page.url,
                f"Redirects to {page.final_url}.{_linked_from(referrers)}",
                referrers,
            )


def _duplicates(crawl: CrawlResult, field: str, code: str) -> Iterator[Issue]:
    groups: dict[str, list[str]] = defaultdict(list)
    for page in crawl.pages.values():
        value = getattr(page, field)
        if value and _indexable(page):
            groups[value.strip().lower()].append(page.url)
    for urls in groups.values():
        if len(urls) < 2:
            continue
        for url in urls:
            others = [u for u in urls if u != url]
            yield issue(code, url, f"Same {field} as {len(others)} other page(s).", others)


@site_check
def check_duplicate_titles(crawl: CrawlResult) -> Iterator[Issue]:
    yield from _duplicates(crawl, "title", "title-duplicate")


@site_check
def check_duplicate_descriptions(crawl: CrawlResult) -> Iterator[Issue]:
    yield from _duplicates(crawl, "description", "description-duplicate")


@site_check
def check_canonical_targets(crawl: CrawlResult) -> Iterator[Issue]:
    for page in crawl.pages.values():
        if not page.is_indexable_html or page.canonical in (None, page.url):
            continue
        target = crawl.pages.get(page.canonical)
        if target is None:
            continue  # not crawled: external, blocked, or beyond the page limit
        if target.error or not target.ok:
            yield issue(
                "canonical-broken",
                page.url,
                f"Canonical {target.url} returns {_describe_failure(target)}.",
                [target.url],
            )
        elif target.redirects:
            yield issue(
                "canonical-redirect",
                page.url,
                f"Canonical {target.url} redirects to {target.final_url}.",
                [target.url, target.final_url],
            )
        elif target.noindex:
            yield issue(
                "canonical-noindex", page.url, f"Canonical {target.url} is noindex.", [target.url]
            )


@site_check
def check_hreflang_targets(crawl: CrawlResult) -> Iterator[Issue]:
    for page in crawl.pages.values():
        if not page.is_indexable_html or not page.hreflang:
            continue
        own = {page.url, page.canonical}
        for alt in page.hreflang:
            if alt.href in own:
                continue
            target = crawl.pages.get(alt.href)
            if target is None:
                continue
            if target.error or not target.ok or target.redirects:
                result = (
                    f"redirects to {target.final_url}"
                    if target.redirects and target.ok
                    else f"returns {_describe_failure(target)}"
                )
                message = f"hreflang {alt.lang}: {alt.href} {result}."
                yield issue("hreflang-broken", page.url, message, [alt.href])
            elif not own & {back.href for back in target.hreflang}:
                yield issue(
                    "hreflang-not-reciprocal",
                    page.url,
                    f"hreflang {alt.lang}: {alt.href} does not link back to this page.",
                    [alt.href],
                )


@site_check
def check_robots_txt(crawl: CrawlResult) -> Iterator[Issue]:
    if crawl.robots is None:
        status = crawl.robots_status
        found = f"HTTP {status}" if status is not None else "no response"
        yield issue("robots-missing", crawl.robots_url, f"robots.txt returned {found}.")
    elif not crawl.robots.sitemaps:
        yield issue("robots-no-sitemap", crawl.robots_url, "No Sitemap line in robots.txt.")
    for url, sources in sorted(crawl.blocked.items()):
        referrers = sorted(sources - {SITEMAP_REFERRER})
        if referrers:
            yield issue(
                "robots-blocked",
                url,
                f"Disallowed by robots.txt.{_linked_from(referrers)}",
                referrers,
            )


@site_check
def check_sitemap_files(crawl: CrawlResult) -> Iterator[Issue]:
    declared = bool(crawl.robots and crawl.robots.sitemaps)
    if not crawl.sitemaps:
        return  # sitemaps were not requested
    for entry in crawl.sitemaps:
        if entry.status is not None and 200 <= entry.status < 300 and not entry.error:
            continue
        problem = entry.error or f"HTTP {entry.status}"
        if not declared and entry is crawl.sitemaps[0] and entry.status == 404:
            yield issue(
                "sitemap-missing",
                entry.url,
                "No Sitemap line in robots.txt and /sitemap.xml returns 404.",
            )
        else:
            yield issue("sitemap-invalid", entry.url, f"Sitemap: {problem}.")


@site_check
def check_sitemap_urls(crawl: CrawlResult) -> Iterator[Issue]:
    in_sitemap = set(crawl.sitemap_urls)
    reached = _reached_by_links(crawl)
    start = crawl.pages.get(crawl.start_url)
    reached |= {crawl.start_url, start.final_url} if start else {crawl.start_url}
    for url in crawl.sitemap_urls:
        if not is_internal(url, crawl.site_host):
            yield issue("sitemap-other-host", url, f"Listed in the sitemap of {crawl.site_host}.")
            continue
        page = crawl.pages.get(url)
        if page is None:
            continue
        if page.error or not page.ok:
            yield issue(
                "sitemap-error", url, f"Listed in the sitemap, returns {_describe_failure(page)}."
            )
        elif page.redirects:
            yield issue(
                "sitemap-redirect",
                url,
                f"Listed in the sitemap, redirects to {page.final_url}.",
                [page.final_url],
            )
        elif page.noindex:
            yield issue("sitemap-noindex", url, "Listed in the sitemap but set to noindex.")
        elif page.is_html and not _is_canonical_self(page):
            yield issue(
                "sitemap-non-canonical",
                url,
                f"Listed in the sitemap, canonical is {page.canonical}.",
                [page.canonical or ""],
            )
        elif _indexable(page) and url not in reached and not crawl.limit_reached:
            yield issue("sitemap-orphan", url, "No crawled page links here.")
    for url, sources in sorted(crawl.blocked.items()):
        if SITEMAP_REFERRER in sources:
            yield issue("sitemap-blocked", url, "Listed in the sitemap, disallowed by robots.txt.")
    if not in_sitemap:
        return
    for page in crawl.pages.values():
        if _indexable(page) and page.url not in in_sitemap:
            yield issue("not-in-sitemap", page.url, "Indexable page not listed in the sitemap.")
