"""Per-page checks. Each one takes a Page and returns the issues it finds."""

import re
from collections.abc import Callable, Iterator

from siteaudit.checks.rules import issue
from siteaudit.models import Issue, Page

PageCheck = Callable[[Page], Iterator[Issue]]
PAGE_CHECKS: list[PageCheck] = []

TITLE_MIN, TITLE_MAX = 30, 60
DESCRIPTION_MIN, DESCRIPTION_MAX = 70, 160
SLOW_RESPONSE_MS = 1000
LARGE_HTML_BYTES = 1024 * 1024

# language, optional script, optional region (ISO 3166-1 alpha-2 or UN M.49)
HREFLANG_RE = re.compile(r"^(x-default|[a-z]{2,3}(-[a-z]{4})?(-([a-z]{2}|\d{3}))?)$")


def page_check(func: PageCheck) -> PageCheck:
    PAGE_CHECKS.append(func)
    return func


def run_page_checks(page: Page) -> list[Issue]:
    """Run every content check on a 2xx HTML page served at its own URL."""
    if not page.is_indexable_html:
        return []
    return [found for check in PAGE_CHECKS for found in check(page)]


@page_check
def check_title(page: Page) -> Iterator[Issue]:
    if not page.title:
        yield issue("title-missing", page.url, "The page has no title.")
        return
    if page.title_count > 1:
        yield issue("title-multiple", page.url, f"{page.title_count} <title> tags.")
    length = len(page.title)
    if length > TITLE_MAX:
        yield issue("title-too-long", page.url, f"{length} characters: {page.title}")
    elif length < TITLE_MIN:
        yield issue("title-too-short", page.url, f"{length} characters: {page.title}")


@page_check
def check_description(page: Page) -> Iterator[Issue]:
    if not page.description:
        yield issue("description-missing", page.url, "The page has no meta description.")
        return
    if page.description_count > 1:
        yield issue("description-multiple", page.url, f"{page.description_count} descriptions.")
    length = len(page.description)
    if length > DESCRIPTION_MAX:
        yield issue("description-too-long", page.url, f"{length} characters.")
    elif length < DESCRIPTION_MIN:
        yield issue("description-too-short", page.url, f"{length} characters.")


@page_check
def check_h1(page: Page) -> Iterator[Issue]:
    if not page.h1:
        yield issue("h1-missing", page.url, "The page has no <h1>.")
    elif len(page.h1) > 1:
        yield issue("h1-multiple", page.url, f"{len(page.h1)} <h1> tags.", related=page.h1)


@page_check
def check_lang(page: Page) -> Iterator[Issue]:
    if not page.lang:
        yield issue("lang-missing", page.url, "<html> has no lang attribute.")


@page_check
def check_viewport(page: Page) -> Iterator[Issue]:
    if not page.viewport:
        yield issue("viewport-missing", page.url, "No viewport meta tag.")


@page_check
def check_images_alt(page: Page) -> Iterator[Issue]:
    missing = page.images_without_alt
    if missing:
        yield issue(
            "img-alt-missing",
            page.url,
            f"{len(missing)} of {page.image_count} images have no alt attribute.",
            related=missing,
        )


@page_check
def check_robots_directives(page: Page) -> Iterator[Issue]:
    sources = []
    if page.meta_robots:
        sources.append("meta robots")
    if page.x_robots_tag:
        sources.append("X-Robots-Tag")
    where = " and ".join(sources)
    if page.noindex:
        yield issue("noindex", page.url, f"noindex is set in {where}.")
    if page.nofollow:
        yield issue("nofollow", page.url, f"nofollow is set in {where}.")


@page_check
def check_canonical(page: Page) -> Iterator[Issue]:
    if page.canonical is None:
        yield issue("canonical-missing", page.url, "No canonical link.")
        return
    if page.canonical_count > 1:
        yield issue("canonical-multiple", page.url, f"{page.canonical_count} canonical links.")
    # A URL with query parameters that points to the same path without them is the
    # standard setup for filters and tracking parameters, not something to review.
    if page.canonical != page.url and page.canonical != page.url.split("?", 1)[0]:
        yield issue(
            "canonical-other", page.url, f"Canonical: {page.canonical}", related=[page.canonical]
        )


@page_check
def check_hreflang(page: Page) -> Iterator[Issue]:
    if not page.hreflang:
        return
    invalid = sorted({alt.lang for alt in page.hreflang if not HREFLANG_RE.match(alt.lang)})
    if invalid:
        yield issue("hreflang-invalid", page.url, f"Invalid codes: {', '.join(invalid)}.")
    self_url = page.canonical or page.url
    if all(alt.href not in (page.url, self_url) for alt in page.hreflang):
        yield issue("hreflang-no-self", page.url, "The hreflang set does not include this page.")


@page_check
def check_json_ld(page: Page) -> Iterator[Issue]:
    for block in page.json_ld:
        if not block.valid:
            yield issue("json-ld-invalid", page.url, block.error or "Invalid JSON.")


@page_check
def check_performance(page: Page) -> Iterator[Issue]:
    if page.response_ms > SLOW_RESPONSE_MS:
        yield issue("slow-response", page.url, f"Server responded in {page.response_ms:.0f} ms.")
    if page.truncated or page.size > LARGE_HTML_BYTES:
        size = "more than 5 MB" if page.truncated else f"{page.size / 1024:.0f} KB"
        yield issue("html-too-large", page.url, f"HTML is {size}.")
