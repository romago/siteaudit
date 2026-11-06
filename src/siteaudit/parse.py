"""Turn a fetched response into a Page model."""

from selectolax.lexbor import LexborHTMLParser

from siteaudit.fetch import FetchResult
from siteaudit.models import Hreflang, Page
from siteaudit.urls import is_internal, normalize_url


def _rel_tokens(value: str | None) -> set[str]:
    return set((value or "").lower().split())


def parse_page(result: FetchResult, site_host: str, found_via: list[str] | None = None) -> Page:
    page = Page(
        url=result.url,
        final_url=result.final_url,
        status=result.status,
        redirects=list(result.redirects),
        error=result.error,
        content_type=result.content_type,
        response_ms=round(result.response_ms, 1),
        size=result.size,
        found_via=list(found_via or []),
    )
    if result.ok and result.is_html and result.content:
        _parse_html(page, result.text, site_host)
    return page


def _parse_html(page: Page, html: str, site_host: str) -> None:
    tree = LexborHTMLParser(html)
    base = page.final_url
    base_node = tree.css_first("head base[href]")
    if base_node is not None:
        base = normalize_url(base_node.attributes.get("href") or "", base=base) or base

    links: dict[str, None] = {}
    external = 0
    for node in tree.css("a[href]"):
        target = normalize_url(node.attributes.get("href") or "", base=base)
        if target is None:
            continue
        if is_internal(target, site_host):
            links.setdefault(target, None)
        else:
            external += 1
    page.links = list(links)
    page.external_links = external

    for node in tree.css("head link[rel][href]"):
        rel = _rel_tokens(node.attributes.get("rel"))
        href = normalize_url(node.attributes.get("href") or "", base=base)
        if href is None:
            continue
        if "canonical" in rel and page.canonical is None:
            page.canonical = href
        elif "alternate" in rel and node.attributes.get("hreflang"):
            lang = (node.attributes.get("hreflang") or "").strip().lower()
            page.hreflang.append(Hreflang(lang=lang, href=href))
