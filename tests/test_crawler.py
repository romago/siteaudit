import pytest
import respx

from siteaudit.crawler import CrawlOptions, crawl
from tests.conftest import FakeSite


@pytest.fixture
def fake(site: FakeSite) -> FakeSite:
    site.redirect("/old-page", "/about")
    site.add("/gone", status=410, body="gone")
    return site


async def test_crawls_whole_site(fake: FakeSite) -> None:
    result = await crawl("https://example.com")
    assert set(result.pages) == {
        "https://example.com/",
        "https://example.com/about",
        "https://example.com/blog/",
        "https://example.com/blog/post-1",
        "https://example.com/contact.html",
        "https://example.com/old-page",
        "https://example.com/missing",
        "https://example.com/orphan",
        "https://example.com/gone",
    }
    assert not result.limit_reached


async def test_redirect_target_is_not_fetched_twice(fake: FakeSite) -> None:
    fake.redirect("/blog/post-1", "/blog/first-post")
    fake.add("/blog/first-post", body="<html><body><a href='/blog/'>Blog</a></body></html>")
    result = await crawl("https://example.com/")
    assert fake.requests.count("/blog/first-post") == 1
    assert result.pages["https://example.com/blog/first-post"].found_via == ["redirect"]


async def test_robots_and_sitemaps(fake: FakeSite) -> None:
    result = await crawl("https://example.com/")
    assert result.robots_status == 200
    assert result.robots is not None
    assert [s.url for s in result.sitemaps] == [
        "https://example.com/sitemap.xml",
        "https://example.com/sitemap-pages.xml",
    ]
    assert result.sitemaps[0].is_index
    assert result.sitemaps[1].url_count == 5
    assert "https://example.com/orphan" in result.sitemap_urls
    # robots.txt disallows /private/, from a link and from the sitemap
    assert result.blocked == {
        "https://example.com/private/area": {"https://example.com/"},
        "https://example.com/private/secret": {"sitemap.xml"},
    }
    assert not any("/private/" in p for p in fake.requests)


async def test_inlinks_and_found_via(fake: FakeSite) -> None:
    result = await crawl("https://example.com/")
    assert result.inlinks["https://example.com/missing"] == {
        "https://example.com/about",
        "https://example.com/contact.html",
    }
    pages = result.pages
    assert pages["https://example.com/"].found_via[0] == "start"
    assert "sitemap" in pages["https://example.com/"].found_via
    assert pages["https://example.com/orphan"].found_via == ["sitemap"]
    assert pages["https://example.com/missing"].status == 404
    assert "redirect" in pages["https://example.com/about"].found_via


async def test_redirect_is_recorded_with_its_target(fake: FakeSite) -> None:
    result = await crawl("https://example.com/")
    old = result.pages["https://example.com/old-page"]
    assert old.status == 200
    assert old.final_url == "https://example.com/about"
    assert [hop.status for hop in old.redirects] == [301]
    assert old.links == []


async def test_max_pages(fake: FakeSite) -> None:
    result = await crawl("https://example.com/", CrawlOptions(max_pages=3))
    assert len(result.pages) <= 4  # three fetches, one of them may land on a redirect target
    assert result.limit_reached


async def test_ignore_robots(fake: FakeSite) -> None:
    result = await crawl("https://example.com/", CrawlOptions(respect_robots=False))
    assert "https://example.com/private/area" in result.pages
    assert result.blocked == {}


async def test_start_redirect_to_www_adopts_host(
    site: FakeSite, mock_router: respx.MockRouter
) -> None:
    site.redirect("/", "https://www.example.com/")
    www = FakeSite("https://www.example.com")
    www.add("/", body='<html><body><a href="/team">Team</a></body></html>')
    www.add("/team", body="<html><body>Team</body></html>")
    mock_router.route(host="www.example.com").mock(side_effect=www.handle)
    result = await crawl("http://example.com", CrawlOptions(use_sitemaps=False))
    assert result.site_host == "www.example.com"
    assert "https://www.example.com/team" in result.pages
    assert result.robots_url == "https://www.example.com/robots.txt"


async def test_no_robots_falls_back_to_sitemap_xml(site: FakeSite) -> None:
    site.add("/robots.txt", status=404, body="nope")
    result = await crawl("https://example.com/")
    assert result.robots is None
    assert result.robots_status == 404
    assert result.sitemaps[0].url == "https://example.com/sitemap.xml"
    assert "https://example.com/private/area" in result.pages


async def test_invalid_start_url() -> None:
    with pytest.raises(ValueError, match="not an http"):
        await crawl("ftp://example.com")
