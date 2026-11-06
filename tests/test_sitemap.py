import gzip

import pytest

from siteaudit.sitemap import SitemapError, parse_sitemap

URLSET = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc> https://example.com/ </loc><lastmod>2026-01-01</lastmod></url>
  <url><loc>https://example.com/about</loc></url>
  <url><lastmod>2026-01-01</lastmod></url>
</urlset>"""

INDEX = b"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/post-sitemap.xml</loc></sitemap>
  <sitemap><loc>https://example.com/page-sitemap.xml</loc></sitemap>
</sitemapindex>"""


def test_urlset() -> None:
    doc = parse_sitemap(URLSET)
    assert doc.urls == ["https://example.com/", "https://example.com/about"]
    assert doc.children == []


def test_index() -> None:
    doc = parse_sitemap(INDEX)
    assert doc.urls == []
    assert doc.children == [
        "https://example.com/post-sitemap.xml",
        "https://example.com/page-sitemap.xml",
    ]


def test_gzipped() -> None:
    assert parse_sitemap(gzip.compress(URLSET)).urls[1] == "https://example.com/about"


def test_without_namespace() -> None:
    assert parse_sitemap(b"<urlset><url><loc>https://e.com/</loc></url></urlset>").urls == [
        "https://e.com/"
    ]


@pytest.mark.parametrize(
    "content",
    [b"<html><body>Not found</body></html>", b"not xml at all", b"\x1f\x8bbroken gzip"],
)
def test_invalid(content: bytes) -> None:
    with pytest.raises(SitemapError):
        parse_sitemap(content)
