from siteaudit.robots import RobotsTxt

WORDPRESS = """
# WordPress default
User-agent: *
Disallow: /wp-admin/
Allow: /wp-admin/admin-ajax.php

Sitemap: https://example.com/wp-sitemap.xml
"""


def test_longest_match_wins_over_order() -> None:
    robots = RobotsTxt.parse(WORDPRESS)
    assert not robots.can_fetch("https://example.com/wp-admin/options.php")
    assert robots.can_fetch("https://example.com/wp-admin/admin-ajax.php")
    assert robots.can_fetch("https://example.com/blog/")
    assert robots.sitemaps == ["https://example.com/wp-sitemap.xml"]


def test_wildcards_and_end_anchor() -> None:
    robots = RobotsTxt.parse("User-agent: *\nDisallow: /*?s=\nDisallow: /*.pdf$\n")
    assert not robots.can_fetch("https://example.com/?s=query")
    assert not robots.can_fetch("https://example.com/files/a.pdf")
    assert robots.can_fetch("https://example.com/files/a.pdf?download=1")
    assert robots.can_fetch("https://example.com/search")


def test_tie_goes_to_allow() -> None:
    robots = RobotsTxt.parse("User-agent: *\nDisallow: /page\nAllow: /page\n")
    assert robots.can_fetch("https://example.com/page")


def test_named_group_replaces_star_group() -> None:
    text = "User-agent: *\nDisallow: /\n\nUser-agent: siteaudit\nUser-agent: other\nDisallow: /x\n"
    robots = RobotsTxt.parse(text)
    assert robots.can_fetch("https://example.com/a", "siteaudit")
    assert not robots.can_fetch("https://example.com/x", "siteaudit")
    assert not robots.can_fetch("https://example.com/a", "googlebot")


def test_empty_disallow_allows_everything() -> None:
    robots = RobotsTxt.parse("User-agent: *\nDisallow:\n")
    assert robots.can_fetch("https://example.com/anything")


def test_robots_txt_itself_is_always_allowed() -> None:
    robots = RobotsTxt.parse("User-agent: *\nDisallow: /\n")
    assert robots.can_fetch("https://example.com/robots.txt")
    assert not robots.can_fetch("https://example.com/")


def test_rules_before_any_user_agent_are_ignored() -> None:
    robots = RobotsTxt.parse("Disallow: /\nUser-agent: *\nDisallow: /a\n")
    assert robots.can_fetch("https://example.com/b")
