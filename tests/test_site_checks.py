from siteaudit.checks.site import SITE_CHECKS, run_site_checks
from siteaudit.crawler import CrawlResult, SitemapFetch
from siteaudit.models import Hop, Hreflang, Issue, Page
from siteaudit.robots import RobotsTxt
from tests.helpers import GOOD_DESCRIPTION

BASE = "https://example.com"


def html(path: str, **fields: object) -> Page:
    url = BASE + path
    defaults: dict[str, object] = {
        "final_url": url,
        "status": 200,
        "content_type": "text/html",
        "title": f"Title of {path}",
        "description": f"{GOOD_DESCRIPTION} {path}",
        "canonical": url,
    }
    return Page(url=url, **(defaults | fields))


def crawl_of(*pages: Page, **fields: object) -> CrawlResult:
    defaults: dict[str, object] = {
        "robots": RobotsTxt.parse(f"User-agent: *\nDisallow:\nSitemap: {BASE}/sitemap.xml"),
        "robots_url": f"{BASE}/robots.txt",
        "robots_status": 200,
        "sitemaps": [SitemapFetch(url=f"{BASE}/sitemap.xml", status=200, url_count=1)],
    }
    result = CrawlResult(start_url=f"{BASE}/", site_host="example.com", **(defaults | fields))  # type: ignore[arg-type]
    result.pages = {page.url: page for page in pages}
    if "sitemap_urls" not in fields:
        result.sitemap_urls = [page.url for page in pages if page.is_indexable_html]
    for page in pages:
        for link in page.links:
            result.inlinks.setdefault(link, set()).add(page.url)
    return result


def by_code(issues: list[Issue], code: str) -> list[Issue]:
    return [i for i in issues if i.code == code]


def test_clean_site_has_no_issues() -> None:
    home = html("/", links=[f"{BASE}/about"])
    about = html("/about", links=[f"{BASE}/"])
    assert run_site_checks(crawl_of(home, about)) == []


def test_every_check_is_registered() -> None:
    assert len(SITE_CHECKS) == 9


def test_broken_links_list_referrers() -> None:
    home = html("/", links=[f"{BASE}/missing", f"{BASE}/error", f"{BASE}/down"])
    other = html("/other", links=[f"{BASE}/missing", f"{BASE}/"])
    missing = Page(url=f"{BASE}/missing", final_url=f"{BASE}/missing", status=404)
    error = Page(url=f"{BASE}/error", final_url=f"{BASE}/error", status=503)
    down = Page(url=f"{BASE}/down", final_url=f"{BASE}/down", error="timeout")
    issues = run_site_checks(crawl_of(home, other, missing, error, down))
    [broken] = by_code(issues, "http-4xx")
    assert broken.url == f"{BASE}/missing"
    assert broken.related == [f"{BASE}/", f"{BASE}/other"]
    assert broken.message == "HTTP 404. Linked from 2 pages."
    assert by_code(issues, "http-5xx")[0].message == "HTTP 503. Linked from 1 page."
    assert by_code(issues, "fetch-failed")[0].message == "timeout. Linked from 1 page."


def test_redirect_chain_loop_and_links_to_redirects() -> None:
    home = html("/", links=[f"{BASE}/old", f"{BASE}/loop"])
    old = html(
        "/old",
        final_url=f"{BASE}/new",
        redirects=[
            Hop(url=f"{BASE}/old", status=301),
            Hop(url="http://example.com/new", status=301),
        ],
    )
    loop = Page(
        url=f"{BASE}/loop",
        final_url=f"{BASE}/loop",
        error="redirect loop",
        redirects=[Hop(url=f"{BASE}/loop", status=302), Hop(url=f"{BASE}/loop2", status=302)],
    )
    issues = run_site_checks(crawl_of(home, old, loop, html("/new")))
    [chain] = by_code(issues, "redirect-chain")
    assert chain.url == f"{BASE}/old"
    assert chain.related == [f"{BASE}/old", "http://example.com/new", f"{BASE}/new"]
    assert "(301 -> 301)" in chain.message
    [linked] = by_code(issues, "link-to-redirect")
    assert linked.related == [f"{BASE}/"]
    [looped] = by_code(issues, "redirect-loop")
    assert looped.related == [f"{BASE}/loop", f"{BASE}/loop2"]


def test_duplicate_titles_and_descriptions() -> None:
    a = html("/a", title="Same title", description="Same description")
    b = html("/b", title="same title ", description="Same description")
    c = html("/c", title="Same title", meta_robots="noindex")
    issues = run_site_checks(crawl_of(a, b, c))
    titles = by_code(issues, "title-duplicate")
    assert [(i.url, i.related) for i in titles] == [(a.url, [b.url]), (b.url, [a.url])]
    assert len(by_code(issues, "description-duplicate")) == 2


def test_canonical_targets() -> None:
    pages = [
        html("/a", canonical=f"{BASE}/gone"),
        html("/b", canonical=f"{BASE}/moved"),
        html("/c", canonical=f"{BASE}/hidden"),
        html("/d", canonical=f"{BASE}/not-crawled"),
        Page(url=f"{BASE}/gone", final_url=f"{BASE}/gone", status=404),
        html("/moved", final_url=f"{BASE}/x", redirects=[Hop(url=f"{BASE}/moved", status=301)]),
        html("/hidden", meta_robots="noindex"),
    ]
    issues = run_site_checks(crawl_of(*pages))
    assert [i.url for i in by_code(issues, "canonical-broken")] == [f"{BASE}/a"]
    assert [i.url for i in by_code(issues, "canonical-redirect")] == [f"{BASE}/b"]
    assert [i.url for i in by_code(issues, "canonical-noindex")] == [f"{BASE}/c"]


def test_hreflang_targets() -> None:
    en = html(
        "/en/",
        hreflang=[
            Hreflang(lang="en", href=f"{BASE}/en/"),
            Hreflang(lang="de", href=f"{BASE}/de/"),
            Hreflang(lang="fr", href=f"{BASE}/fr/"),
            Hreflang(lang="es", href=f"{BASE}/es/"),
        ],
    )
    de = html("/de/", hreflang=[Hreflang(lang="en", href=f"{BASE}/en/")])
    fr = html("/fr/", hreflang=[Hreflang(lang="fr", href=f"{BASE}/fr/")])
    es = Page(url=f"{BASE}/es/", final_url=f"{BASE}/es/", status=404)
    issues = run_site_checks(crawl_of(en, de, fr, es))
    # de links back to en; fr does not
    assert [(i.url, i.related) for i in by_code(issues, "hreflang-not-reciprocal")] == [
        (f"{BASE}/en/", [f"{BASE}/fr/"])
    ]
    [broken] = by_code(issues, "hreflang-broken")
    assert broken.message == f"hreflang es: {BASE}/es/ returns HTTP 404."


def test_robots_txt() -> None:
    home = html("/", links=[f"{BASE}/private"])
    missing = run_site_checks(crawl_of(home, robots=None, robots_status=404))
    assert by_code(missing, "robots-missing")[0].message == "robots.txt returned HTTP 404."

    no_sitemap = crawl_of(home, robots=RobotsTxt.parse("User-agent: *\nDisallow: /private"))
    no_sitemap.blocked = {f"{BASE}/private": {f"{BASE}/"}, f"{BASE}/secret": {"sitemap.xml"}}
    issues = run_site_checks(no_sitemap)
    assert len(by_code(issues, "robots-no-sitemap")) == 1
    [blocked] = by_code(issues, "robots-blocked")
    assert blocked.related == [f"{BASE}/"]
    assert [i.url for i in by_code(issues, "sitemap-blocked")] == [f"{BASE}/secret"]


def test_sitemap_files() -> None:
    home = html("/")
    fallback = [SitemapFetch(url=f"{BASE}/sitemap.xml", status=404)]
    issues = run_site_checks(crawl_of(home, robots=None, robots_status=404, sitemaps=fallback))
    assert len(by_code(issues, "sitemap-missing")) == 1

    declared = [
        SitemapFetch(url=f"{BASE}/sitemap.xml", status=200, error="invalid XML: syntax error"),
        SitemapFetch(url=f"{BASE}/posts.xml", status=500),
    ]
    issues = run_site_checks(crawl_of(home, sitemaps=declared))
    assert [i.message for i in by_code(issues, "sitemap-invalid")] == [
        "Sitemap: invalid XML: syntax error.",
        "Sitemap: HTTP 500.",
    ]


def test_sitemap_urls() -> None:
    pages = [
        html("/", links=[f"{BASE}/linked", f"{BASE}/old"]),
        html("/linked"),
        html("/orphan"),
        html("/unlisted", links=[f"{BASE}/"]),
        Page(url=f"{BASE}/gone", final_url=f"{BASE}/gone", status=410),
        html("/old", final_url=f"{BASE}/new", redirects=[Hop(url=f"{BASE}/old", status=301)]),
        html("/new"),
        html("/hidden", meta_robots="noindex"),
        html("/dup", canonical=f"{BASE}/linked"),
    ]
    paths = ("/", "/linked", "/orphan", "/gone", "/old", "/new", "/hidden", "/dup")
    listed = [f"{BASE}{p}" for p in paths]
    issues = run_site_checks(crawl_of(*pages, sitemap_urls=listed))
    assert [i.url for i in by_code(issues, "sitemap-error")] == [f"{BASE}/gone"]
    assert [i.url for i in by_code(issues, "sitemap-redirect")] == [f"{BASE}/old"]
    assert [i.url for i in by_code(issues, "sitemap-noindex")] == [f"{BASE}/hidden"]
    assert [i.url for i in by_code(issues, "sitemap-non-canonical")] == [f"{BASE}/dup"]
    # /new is reached through the redirect from /old, so it is not an orphan
    assert [i.url for i in by_code(issues, "sitemap-orphan")] == [f"{BASE}/orphan"]
    assert [i.url for i in by_code(issues, "not-in-sitemap")] == [f"{BASE}/unlisted"]


def test_orphans_are_not_reported_when_the_crawl_was_cut_short() -> None:
    result = crawl_of(html("/"), html("/orphan"), limit_reached=True)
    assert by_code(run_site_checks(result), "sitemap-orphan") == []
