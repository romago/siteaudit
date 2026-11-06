"""Turn a fetched response into a Page model."""

import json
from typing import Any

from selectolax.lexbor import LexborHTMLParser, LexborNode

from siteaudit.fetch import FetchResult
from siteaudit.models import Hreflang, JsonLd, Page
from siteaudit.urls import is_internal, normalize_url


def _rel_tokens(value: str | None) -> set[str]:
    return set((value or "").lower().split())


def _attr(node: LexborNode, name: str) -> str:
    return (node.attributes.get(name) or "").strip()


def _text(node: LexborNode) -> str:
    return " ".join(node.text(deep=True).split())


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
        truncated=result.truncated,
        found_via=list(found_via or []),
        x_robots_tag=", ".join(result.headers.get_list("x-robots-tag")) or None,
    )
    if result.ok and result.is_html and result.content:
        parse_html(page, result.text, site_host)
    return page


def parse_html(page: Page, html: str, site_host: str) -> None:
    """Fill the content fields of ``page`` from its HTML."""
    tree = LexborHTMLParser(html)
    base = page.final_url
    base_node = tree.css_first("base[href]")
    if base_node is not None:
        base = normalize_url(_attr(base_node, "href"), base=base) or base

    html_node = tree.css_first("html")
    if html_node is not None:
        page.lang = _attr(html_node, "lang") or None

    titles = tree.css("head title")
    page.title_count = len(titles)
    if titles:
        page.title = _text(titles[0])

    descriptions: list[str] = []
    robots: list[str] = []
    for meta in tree.css("meta[name]"):
        name = _attr(meta, "name").lower()
        content = " ".join(_attr(meta, "content").split())
        if name == "description":
            descriptions.append(content)
        elif name in ("robots", "googlebot"):
            robots.append(content)
        elif name == "viewport":
            page.viewport = True
    page.description_count = len(descriptions)
    page.description = descriptions[0] if descriptions else None
    page.meta_robots = ", ".join(r for r in robots if r) or None

    page.h1 = [_text(node) for node in tree.css("h1")]

    canonicals: list[str] = []
    for node in tree.css("link[rel][href]"):
        rel = _rel_tokens(node.attributes.get("rel"))
        href = normalize_url(_attr(node, "href"), base=base)
        if href is None:
            continue
        if "canonical" in rel:
            canonicals.append(href)
        elif "alternate" in rel and _attr(node, "hreflang"):
            page.hreflang.append(Hreflang(lang=_attr(node, "hreflang").lower(), href=href))
    page.canonical_count = len(canonicals)
    page.canonical = canonicals[0] if canonicals else None

    images = tree.css("img")
    page.image_count = len(images)
    page.images_without_alt = [
        _attr(img, "src") or _attr(img, "data-src") or "(no src)"
        for img in images
        if "alt" not in img.attributes
    ]

    page.json_ld = [
        _parse_json_ld(node.text(deep=True))
        for node in tree.css("script")
        if _attr(node, "type").lower() == "application/ld+json"
    ]

    links: dict[str, None] = {}
    external = 0
    for node in tree.css("a[href]"):
        target = normalize_url(_attr(node, "href"), base=base)
        if target is None:
            continue
        if is_internal(target, site_host):
            links.setdefault(target, None)
        else:
            external += 1
    page.links = list(links)
    page.external_links = external


def _parse_json_ld(text: str) -> JsonLd:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return JsonLd(valid=False, error=f"{exc.msg} at line {exc.lineno}, column {exc.colno}")
    types: dict[str, None] = {}
    _collect_types(data, types)
    return JsonLd(valid=True, types=list(types))


def _collect_types(data: Any, found: dict[str, None]) -> None:
    """Collect ``@type`` of top-level entities and of ``@graph`` members, not nested ones."""
    if isinstance(data, list):
        for item in data:
            _collect_types(item, found)
        return
    if not isinstance(data, dict):
        return
    kind = data.get("@type")
    for value in kind if isinstance(kind, list) else [kind]:
        if isinstance(value, str):
            found.setdefault(value, None)
    if "@graph" in data:
        _collect_types(data["@graph"], found)
