"""Builders for Page objects in tests."""

import httpx

from siteaudit.fetch import FetchResult
from siteaudit.models import Page
from siteaudit.parse import parse_page

GOOD_DESCRIPTION = "A meta description that is long enough to pass the check and short enough too."
GOOD_HEAD = f"""
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>A good page title that is long enough</title>
<meta name="description" content="{GOOD_DESCRIPTION}">
<link rel="canonical" href="{{url}}">
"""


def make_page(
    body: str = "<h1>Heading</h1>",
    *,
    head: str | None = None,
    url: str = "https://example.com/page",
    status: int = 200,
    headers: dict[str, str] | None = None,
    lang: str | None = "en",
    response_ms: float = 100.0,
) -> Page:
    """Parse an HTML document built from ``head`` and ``body`` as if it was fetched."""
    head = GOOD_HEAD.format(url=url) if head is None else head
    lang_attr = f' lang="{lang}"' if lang else ""
    html = f"<!doctype html><html{lang_attr}><head>{head}</head><body>{body}</body></html>"
    hdrs = httpx.Headers({"content-type": "text/html; charset=utf-8", **(headers or {})})
    content = html.encode()
    result = FetchResult(
        url=url,
        final_url=url,
        status=status,
        headers=hdrs,
        content=content,
        size=len(content),
        response_ms=response_ms,
    )
    return parse_page(result, "example.com")
