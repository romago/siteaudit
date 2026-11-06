"""The catalogue of issue codes: severity, a title for grouping, and how to fix it."""

from dataclasses import dataclass

from siteaudit.models import Issue, Severity

E, W, N = Severity.ERROR, Severity.WARNING, Severity.NOTICE


@dataclass(frozen=True, slots=True)
class Rule:
    code: str
    severity: Severity
    title: str
    fix: str


_RULES = [
    # status and redirects
    Rule("http-4xx", E, "Broken page or link (4xx)",
         "Restore the page, or fix the links on the pages that link to it."),
    Rule("http-5xx", E, "Page returns a 5xx error", "Check the server logs for this URL."),
    Rule("fetch-failed", E, "Page could not be fetched", "Check that the server responds in time."),
    Rule("redirect-loop", E, "Redirect loop", "Fix the redirect rules so the chain ends."),
    Rule("redirect-chain", W, "Redirect chain", "Redirect straight to the final URL in one hop."),
    Rule("link-to-redirect", N, "Internal link to a redirect",
         "Update the links on the listed pages to point to the final URL."),
    # title and description
    Rule("title-missing", E, "Missing <title>", "Add a unique, descriptive title."),
    Rule("title-multiple", W, "More than one <title>", "Keep one <title> in <head>."),
    Rule("title-too-long", W, "Title is too long", "Keep titles under 60 characters."),
    Rule("title-too-short", N, "Title is too short", "Use at least 30 characters."),
    Rule("title-duplicate", W, "Duplicate title", "Give each page its own title."),
    Rule("description-missing", W, "Missing meta description",
         "Add a meta description of 70-160 characters."),
    Rule("description-multiple", W, "More than one meta description", "Keep one."),
    Rule("description-too-long", N, "Meta description is too long",
         "Keep descriptions under 160 characters."),
    Rule("description-too-short", N, "Meta description is too short",
         "Use at least 70 characters."),
    Rule("description-duplicate", W, "Duplicate meta description",
         "Give each page its own description."),
    # structure
    Rule("h1-missing", W, "Missing <h1>", "Add one <h1> with the main topic of the page."),
    Rule("h1-multiple", N, "More than one <h1>", "Use one <h1> and <h2>-<h6> for sections."),
    Rule("lang-missing", W, "Missing lang on <html>", 'Add lang, for example <html lang="en">.'),
    Rule("viewport-missing", W, "Missing viewport meta tag",
         'Add <meta name="viewport" content="width=device-width, initial-scale=1">.'),
    Rule("img-alt-missing", W, "Images without alt",
         'Add alt text, or alt="" for decorative images.'),
    # indexing
    Rule("noindex", W, "Page is set to noindex",
         "Remove noindex if the page should appear in search."),
    Rule("nofollow", N, "Page is set to nofollow", "Remove nofollow unless it is intended."),
    Rule("canonical-missing", N, "Missing canonical", "Add a self-referencing canonical link."),
    Rule("canonical-multiple", W, "More than one canonical", "Keep one canonical link."),
    Rule("canonical-other", N, "Canonical points to another URL",
         "Check that this page is meant to be a duplicate of the canonical URL."),
    Rule("canonical-broken", E, "Canonical points to an error page",
         "Point the canonical to a page that returns 200."),
    Rule("canonical-redirect", W, "Canonical points to a redirect",
         "Point the canonical to the final URL."),
    Rule("canonical-noindex", E, "Canonical points to a noindex page",
         "Point the canonical to an indexable page."),
    # hreflang
    Rule("hreflang-invalid", W, "Invalid hreflang code",
         "Use ISO 639-1 language and ISO 3166-1 region codes, such as en or en-us."),
    Rule("hreflang-no-self", W, "hreflang without a self reference",
         "Include the page itself in its hreflang set."),
    Rule("hreflang-broken", E, "hreflang points to an error or redirect",
         "Point hreflang links to pages that return 200."),
    Rule("hreflang-not-reciprocal", W, "hreflang is not reciprocal",
         "The target page must link back with its own hreflang set."),
    # structured data
    Rule("json-ld-invalid", E, "Invalid JSON-LD",
         "Fix the JSON syntax of the structured data block."),
    # performance
    Rule("slow-response", W, "Slow server response", "Aim for a server response under 1 second."),
    Rule("html-too-large", W, "HTML is very large", "Keep the HTML document under 1 MB."),
    # sitemap and robots.txt
    Rule("robots-missing", W, "robots.txt is missing", "Add a robots.txt with a Sitemap line."),
    Rule("robots-no-sitemap", N, "robots.txt has no Sitemap line",
         "Add Sitemap: https://your-site/sitemap.xml to robots.txt."),
    Rule("robots-blocked", N, "Linked page blocked by robots.txt",
         "Check that blocking it is intended."),
    Rule("sitemap-missing", W, "No sitemap found",
         "Publish a sitemap.xml and list it in robots.txt."),
    Rule("sitemap-invalid", E, "Sitemap cannot be read", "Fix the sitemap XML or its URL."),
    Rule("sitemap-error", E, "Sitemap URL returns an error",
         "Remove the URL from the sitemap or restore the page."),
    Rule("sitemap-redirect", W, "Sitemap URL redirects", "List the final URL in the sitemap."),
    Rule("sitemap-noindex", E, "Sitemap URL is noindex",
         "Remove noindex pages from the sitemap."),
    Rule("sitemap-non-canonical", W, "Sitemap URL has a canonical to another page",
         "List only canonical URLs in the sitemap."),
    Rule("sitemap-blocked", E, "Sitemap URL blocked by robots.txt",
         "Remove it from the sitemap or allow it in robots.txt."),
    Rule("sitemap-orphan", N, "Page only found in the sitemap",
         "Link to it from at least one other page."),
    Rule("not-in-sitemap", N, "Indexable page missing from the sitemap",
         "Add the page to the sitemap."),
]  # fmt: skip

RULES: dict[str, Rule] = {rule.code: rule for rule in _RULES}


def issue(code: str, url: str, message: str, related: list[str] | None = None) -> Issue:
    """Create an Issue with the severity from the catalogue."""
    return Issue(
        code=code,
        severity=RULES[code].severity,
        url=url,
        message=message,
        related=related or [],
    )
