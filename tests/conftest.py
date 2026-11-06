"""Shared fixtures: a small fake site served through respx."""

from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import respx

FIXTURES = Path(__file__).parent / "fixtures"
SITE_DIR = FIXTURES / "site"

_TYPES = {".html": "text/html; charset=utf-8", ".xml": "application/xml", ".txt": "text/plain"}


class FakeSite:
    """Serves files from a directory for one origin, plus routes added per test.

    ``/`` and ``/dir/`` map to ``index.html``, and ``/about`` maps to ``about.html``.
    """

    def __init__(self, origin: str, root: Path = SITE_DIR) -> None:
        self.origin = origin
        self.root = root
        self.routes: dict[str, httpx.Response] = {}
        self.requests: list[str] = []

    def add(self, path: str, status: int = 200, body: str = "", **headers: str) -> None:
        hdrs = {k.replace("_", "-"): v for k, v in headers.items()}
        if body and "content-type" not in {k.lower() for k in hdrs}:
            hdrs["content-type"] = "text/html; charset=utf-8"
        self.routes[path] = httpx.Response(status, headers=hdrs, text=body)

    def redirect(self, path: str, location: str, status: int = 301) -> None:
        self.routes[path] = httpx.Response(status, headers={"location": location})

    def _file_for(self, path: str) -> Path | None:
        rel = path.lstrip("/")
        candidates = [rel + "index.html"] if path.endswith("/") else [rel, rel + ".html"]
        for candidate in candidates:
            file = self.root / candidate
            if file.is_file():
                return file
        return None

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.raw_path.decode()
        self.requests.append(path)
        if path in self.routes:
            return self.routes[path]
        file = self._file_for(request.url.path)
        if file is None:
            return httpx.Response(404, text="not found", headers={"content-type": "text/html"})
        headers = {"content-type": _TYPES.get(file.suffix, "application/octet-stream")}
        return httpx.Response(200, content=file.read_bytes(), headers=headers)


@pytest.fixture
def mock_router() -> Iterator[respx.MockRouter]:
    with respx.mock(assert_all_called=False) as router:
        yield router


@pytest.fixture
def site(mock_router: respx.MockRouter) -> FakeSite:
    fake = FakeSite("https://example.com")
    mock_router.route(host="example.com").mock(side_effect=fake.handle)
    return fake
