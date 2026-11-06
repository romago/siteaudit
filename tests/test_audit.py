from siteaudit.audit import run_audit
from siteaudit.checks.rules import RULES
from siteaudit.models import Severity
from tests.conftest import FakeSite

B = "https://example.com"


async def test_audit_of_fake_site(site: FakeSite) -> None:
    site.redirect("/old-page", "/about")
    site.add("/gone", status=410, body="gone")
    result = await run_audit(f"{B}/")

    found = {(i.code, i.url.removeprefix(B)) for i in result.issues}
    assert found == {
        ("http-4xx", "/missing"),
        ("http-4xx", "/gone"),
        ("sitemap-error", "/gone"),
        ("sitemap-blocked", "/private/secret"),
        ("sitemap-orphan", "/orphan"),
        ("robots-blocked", "/private/area"),
        ("link-to-redirect", "/old-page"),
        ("not-in-sitemap", "/blog/"),
        ("not-in-sitemap", "/blog/post-1"),
        ("not-in-sitemap", "/contact.html"),
        ("canonical-missing", "/blog/"),
        ("canonical-missing", "/blog/post-1"),
        ("canonical-missing", "/contact.html"),
        ("canonical-missing", "/orphan"),
        ("title-too-short", "/about"),
        ("title-too-short", "/blog/"),
        ("title-too-short", "/blog/post-1"),
        ("title-too-short", "/contact.html"),
        ("title-too-short", "/orphan"),
    }
    missing = next(i for i in result.issues if i.url == f"{B}/missing")
    assert missing.related == [f"{B}/about", f"{B}/contact.html"]

    # sorted by severity, then code
    ranks = [i.severity.rank for i in result.issues]
    assert ranks == sorted(ranks)
    assert result.issues[0].severity is Severity.ERROR
    assert len(result.pages) == 9
    assert result.duration_s >= 0
    assert not result.limit_reached


def test_rule_catalogue_is_consistent() -> None:
    for code, rule in RULES.items():
        assert code == rule.code
        assert rule.title
        assert rule.fix.endswith(".")
