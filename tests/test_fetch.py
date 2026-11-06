import httpx
import pytest
import respx

from siteaudit.fetch import decode_body, fetch
from siteaudit.models import Hop
from tests.conftest import FakeSite


@pytest.fixture
async def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(follow_redirects=False)


async def test_html_page(site: FakeSite, client: httpx.AsyncClient) -> None:
    result = await fetch(client, "https://example.com/about")
    assert result.status == 200
    assert result.ok
    assert result.is_html
    assert result.redirects == []
    assert "<title>About Example Studio</title>" in result.text
    assert result.size == len(result.content) > 0
    assert result.response_ms >= 0


async def test_redirect_chain_is_recorded(site: FakeSite, client: httpx.AsyncClient) -> None:
    site.redirect("/a", "http://example.com/b")
    site.redirect("/b", "https://example.com/about", status=302)
    # http://example.com is served by the same fake site
    result = await fetch(client, "https://example.com/a")
    assert result.status == 200
    assert result.final_url == "https://example.com/about"
    assert result.redirects == [
        Hop(url="https://example.com/a", status=301),
        Hop(url="http://example.com/b", status=302),
    ]


async def test_redirect_loop(site: FakeSite, client: httpx.AsyncClient) -> None:
    site.redirect("/a", "/b")
    site.redirect("/b", "/a")
    result = await fetch(client, "https://example.com/a")
    assert result.status is None
    assert result.error == "redirect loop"
    assert len(result.redirects) == 2


async def test_too_many_redirects(site: FakeSite, client: httpx.AsyncClient) -> None:
    for i in range(5):
        site.redirect(f"/r{i}", f"/r{i + 1}")
    result = await fetch(client, "https://example.com/r0", max_redirects=3)
    assert result.error == "too many redirects"
    assert len(result.redirects) == 3


async def test_redirect_to_unsupported_scheme(site: FakeSite, client: httpx.AsyncClient) -> None:
    site.redirect("/mail", "mailto:hi@example.com")
    result = await fetch(client, "https://example.com/mail")
    # httpx refuses to build the next request, which ends up as an error, not a crash
    assert result.status is None
    assert result.error is not None


async def test_not_found(site: FakeSite, client: httpx.AsyncClient) -> None:
    result = await fetch(client, "https://example.com/nope")
    assert result.status == 404
    assert not result.ok


async def test_binary_body_is_not_read(site: FakeSite, client: httpx.AsyncClient) -> None:
    site.add("/file.pdf", body="%PDF-1.7", content_type="application/pdf", content_length="8")
    result = await fetch(client, "https://example.com/file.pdf")
    assert result.status == 200
    assert result.content == b""
    assert result.size == 8


async def test_body_is_truncated_at_limit(site: FakeSite, client: httpx.AsyncClient) -> None:
    site.add("/big", body="x" * 5000)
    result = await fetch(client, "https://example.com/big", max_bytes=1000)
    assert result.truncated
    assert len(result.content) == 1000


async def test_timeout(mock_router: respx.MockRouter, client: httpx.AsyncClient) -> None:
    mock_router.get("https://slow.example.com/").mock(side_effect=httpx.ReadTimeout("slow"))
    result = await fetch(client, "https://slow.example.com/")
    assert result.status is None
    assert result.error == "timeout"


async def test_connection_error(mock_router: respx.MockRouter, client: httpx.AsyncClient) -> None:
    mock_router.get("https://down.example.com/").mock(side_effect=httpx.ConnectError("refused"))
    result = await fetch(client, "https://down.example.com/")
    assert result.error == "ConnectError: refused"


def test_decode_body_charsets() -> None:
    text = "Привет"
    assert decode_body(text.encode("cp1251"), "text/html; charset=windows-1251") == text
    meta = '<meta charset="windows-1251"><p>Привет</p>'.encode("cp1251")
    assert "Привет" in decode_body(meta, "text/html")
    assert decode_body(b"\xff\xfe broken", "text/html") == "�� broken"
