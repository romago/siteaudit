import pytest

from siteaudit.urls import is_internal, normalize_url, site_key


@pytest.mark.parametrize(
    ("url", "base", "expected"),
    [
        ("HTTPS://Example.COM", None, "https://example.com/"),
        ("https://example.com:443/a?b=1#frag", None, "https://example.com/a?b=1"),
        ("http://example.com:8080/", None, "http://example.com:8080/"),
        ("post-1", "https://example.com/blog/", "https://example.com/blog/post-1"),
        ("../", "https://example.com/blog/post-1", "https://example.com/"),
        ("  /about  ", "https://example.com/", "https://example.com/about"),
        ("//cdn.example.com/x", "https://example.com/", "https://cdn.example.com/x"),
        ("mailto:hi@example.com", None, None),
        ("javascript:void(0)", "https://example.com/", None),
        ("tel:+123", None, None),
        ("", "https://example.com/", None),
        ("https://example.com:99999/", None, None),
    ],
)
def test_normalize_url(url: str, base: str | None, expected: str | None) -> None:
    assert normalize_url(url, base=base) == expected


def test_site_key_ignores_www() -> None:
    assert site_key("WWW.Example.com") == "example.com"
    assert is_internal("https://www.example.com/a", "example.com")
    assert is_internal("http://example.com/a", "www.example.com")
    assert not is_internal("https://blog.example.com/", "example.com")
