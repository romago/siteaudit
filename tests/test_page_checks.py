import pytest

from siteaudit.checks.page import PAGE_CHECKS, run_page_checks
from siteaudit.checks.rules import RULES
from siteaudit.models import Issue, Severity
from tests.helpers import make_page

URL = "https://example.com/page"


def codes(issues: list[Issue]) -> list[str]:
    return [i.code for i in issues]


def test_good_page_has_no_issues() -> None:
    assert run_page_checks(make_page()) == []


def test_every_check_is_registered() -> None:
    assert len(PAGE_CHECKS) == 11


def test_only_indexable_html_is_checked() -> None:
    assert run_page_checks(make_page(head="", status=404)) == []


@pytest.mark.parametrize(
    ("title", "code"),
    [
        ("", "title-missing"),
        ("Short", "title-too-short"),
        ("A" * 61, "title-too-long"),
    ],
)
def test_title(title: str, code: str) -> None:
    head = f"<title>{title}</title>" if title else ""
    assert code in codes(run_page_checks(make_page(head=head)))


def test_title_multiple() -> None:
    page = make_page(head="<title>A good page title that is long enough</title><title>Two</title>")
    assert "title-multiple" in codes(run_page_checks(page))


@pytest.mark.parametrize(
    ("description", "code"),
    [
        (None, "description-missing"),
        ("Too short.", "description-too-short"),
        ("x" * 161, "description-too-long"),
    ],
)
def test_description(description: str | None, code: str) -> None:
    meta = f'<meta name="description" content="{description}">' if description else ""
    assert code in codes(run_page_checks(make_page(head=meta)))


def test_description_multiple() -> None:
    meta = '<meta name="description" content="{}">'.format("d" * 100)
    issues = run_page_checks(make_page(head=meta * 2))
    assert "description-multiple" in codes(issues)


def test_h1() -> None:
    assert "h1-missing" in codes(run_page_checks(make_page("<p>No heading</p>")))
    issues = run_page_checks(make_page("<h1>A</h1><h1>B</h1>"))
    multiple = next(i for i in issues if i.code == "h1-multiple")
    assert multiple.related == ["A", "B"]


def test_lang_and_viewport() -> None:
    issues = codes(run_page_checks(make_page(lang=None, head="<title>T</title>")))
    assert "lang-missing" in issues
    assert "viewport-missing" in issues


def test_images_without_alt() -> None:
    issues = run_page_checks(make_page('<h1>H</h1><img src="/a.jpg"><img src="/b.jpg" alt="">'))
    alt = next(i for i in issues if i.code == "img-alt-missing")
    assert alt.related == ["/a.jpg"]
    assert alt.message == "1 of 2 images have no alt attribute."


def test_noindex_and_nofollow() -> None:
    page = make_page(headers={"x-robots-tag": "noindex, nofollow"})
    issues = run_page_checks(page)
    assert codes(issues) == ["noindex", "nofollow"]
    assert issues[0].message == "noindex is set in X-Robots-Tag."
    assert issues[0].severity is Severity.WARNING


def test_canonical() -> None:
    assert "canonical-missing" in codes(run_page_checks(make_page(head="<title>T</title>")))
    other = make_page(head='<link rel="canonical" href="https://example.com/other">')
    assert "canonical-other" in codes(run_page_checks(other))
    variant = make_page(url=f"{URL}?utm_source=x", head=f'<link rel="canonical" href="{URL}">')
    assert "canonical-other" not in codes(run_page_checks(variant))
    other_path = make_page(url=f"{URL}?page=2", head=f'<link rel="canonical" href="{URL}/2">')
    assert "canonical-other" in codes(run_page_checks(other_path))
    two = make_page(head=f'<link rel="canonical" href="{URL}"><link rel="canonical" href="/x">')
    assert "canonical-multiple" in codes(run_page_checks(two))


def test_hreflang() -> None:
    head = '<link rel="alternate" hreflang="en_US" href="/en/">'
    issues = codes(run_page_checks(make_page(head=head)))
    assert "hreflang-invalid" in issues
    assert "hreflang-no-self" in issues

    head = (
        f'<link rel="canonical" href="{URL}">'
        f'<link rel="alternate" hreflang="en" href="{URL}">'
        '<link rel="alternate" hreflang="zh-hant-tw" href="/tw/">'
        '<link rel="alternate" hreflang="es-419" href="/es/">'
        '<link rel="alternate" hreflang="x-default" href="/">'
    )
    issues = codes(run_page_checks(make_page(head=head)))
    assert "hreflang-invalid" not in issues
    assert "hreflang-no-self" not in issues


def test_json_ld_invalid() -> None:
    page = make_page('<h1>H</h1><script type="application/ld+json">{oops}</script>')
    issues = run_page_checks(page)
    assert codes(issues) == ["json-ld-invalid"]
    assert issues[0].severity is Severity.ERROR


def test_performance() -> None:
    slow = make_page(response_ms=2500)
    assert codes(run_page_checks(slow)) == ["slow-response"]
    big = make_page("<h1>H</h1>" + "<p>text</p>" * 100_000)
    assert codes(run_page_checks(big)) == ["html-too-large"]


def test_issue_codes_are_in_catalogue() -> None:
    page = make_page(lang=None, head="", body='<img src="x"><script type="application/ld+json">x')
    for found in run_page_checks(page):
        assert found.code in RULES
        assert found.severity is RULES[found.code].severity
