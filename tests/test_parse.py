import httpx

from siteaudit.fetch import FetchResult
from siteaudit.models import Hop
from siteaudit.parse import parse_page
from tests.helpers import make_page


def test_head_fields() -> None:
    page = make_page(
        head="""
        <base href="https://example.com/docs/">
        <title>  Docs \n home </title>
        <meta name="description" content=" First ">
        <meta name="DESCRIPTION" content="Second">
        <meta name="robots" content="noindex, follow">
        <meta name="viewport" content="width=device-width">
        <link rel="canonical" href="intro">
        <link rel="alternate" hreflang="DE" href="/de/">
        <link rel="alternate" type="application/rss+xml" href="/feed">
        """,
        lang="en-US",
    )
    assert page.title == "Docs home"
    assert page.title_count == 1
    assert page.description == "First"
    assert page.description_count == 2
    assert page.meta_robots == "noindex, follow"
    assert page.noindex
    assert not page.nofollow
    assert page.viewport
    assert page.lang == "en-US"
    assert page.canonical == "https://example.com/docs/intro"
    assert [(h.lang, h.href) for h in page.hreflang] == [("de", "https://example.com/de/")]


def test_body_fields() -> None:
    page = make_page(
        """
        <h1>One <em>big</em> title</h1><h1>Two</h1>
        <img src="a.png" alt="A"><img src="b.png"><img src="c.png" alt=""><img data-src="d.png">
        <a href="/x#top">x</a><a href="/x">x again</a><a href="https://www.example.com/y">y</a>
        <a href="https://other.org/">other</a><a href="tel:123">phone</a>
        """
    )
    assert page.h1 == ["One big title", "Two"]
    assert page.image_count == 4
    assert page.images_without_alt == ["b.png", "d.png"]
    assert page.links == ["https://example.com/x", "https://www.example.com/y"]
    assert page.external_links == 1


def test_json_ld() -> None:
    page = make_page(
        """
        <script type="application/ld+json">
          {"@context": "https://schema.org", "@graph": [
            {"@type": "WebSite", "publisher": {"@type": "Organization"}},
            {"@type": ["Article", "BlogPosting"]}
          ]}
        </script>
        <script type="application/ld+json">[{"@type": "Person"}]</script>
        <script type="application/ld+json">{"@type": "Product",}</script>
        <script>var notJsonLd = 1;</script>
        """
    )
    assert [b.valid for b in page.json_ld] == [True, True, False]
    assert page.json_ld[0].types == ["WebSite", "Article", "BlogPosting"]
    assert page.json_ld[1].types == ["Person"]
    assert page.json_ld[2].error is not None
    assert page.json_ld[2].error.startswith("Expecting property name")


def test_x_robots_tag_header() -> None:
    page = make_page(headers={"x-robots-tag": "googlebot: noindex"})
    assert page.x_robots_tag == "googlebot: noindex"
    assert page.noindex


def test_none_means_noindex_nofollow() -> None:
    page = make_page(head='<meta name="robots" content="NONE">')
    assert page.noindex
    assert page.nofollow


def test_non_html_and_errors_are_not_parsed() -> None:
    result = FetchResult(
        url="https://example.com/a",
        final_url="https://example.com/b",
        status=404,
        redirects=[Hop(url="https://example.com/a", status=301)],
        headers=httpx.Headers({"content-type": "text/html"}),
        content=b"<title>Not found</title>",
    )
    page = parse_page(result, "example.com", ["link"])
    assert page.title is None
    assert page.status == 404
    assert page.redirects[0].status == 301
    assert page.found_via == ["link"]
