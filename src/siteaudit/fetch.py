"""A single HTTP fetch with manual redirect tracking, a timeout and a size limit."""

import re
import time
from dataclasses import dataclass, field

import httpx

from siteaudit.models import Hop
from siteaudit.urls import normalize_url

REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_MAX_REDIRECTS = 10

_TEXT_TYPES = ("text/", "application/xhtml+xml", "application/xml", "application/rss+xml")
_META_CHARSET = re.compile(rb"""<meta[^>]+charset=["']?([\w-]+)""", re.IGNORECASE)


@dataclass(slots=True)
class FetchResult:
    """What came back for one URL after following redirects."""

    url: str
    final_url: str
    status: int | None = None
    redirects: list[Hop] = field(default_factory=list)
    headers: httpx.Headers = field(default_factory=httpx.Headers)
    content: bytes = b""
    response_ms: float = 0.0
    size: int = 0
    truncated: bool = False
    error: str | None = None

    @property
    def content_type(self) -> str:
        value: str = self.headers.get("content-type", "")
        return value.split(";")[0].strip().lower()

    @property
    def is_html(self) -> bool:
        return self.content_type in ("text/html", "application/xhtml+xml")

    @property
    def ok(self) -> bool:
        return self.status is not None and 200 <= self.status < 300

    @property
    def text(self) -> str:
        return decode_body(self.content, self.headers.get("content-type", ""))


def decode_body(content: bytes, content_type: str = "") -> str:
    """Decode a response body using the header charset, a meta charset, then UTF-8."""
    candidates: list[str] = []
    match = re.search(r"charset=([\w-]+)", content_type, re.IGNORECASE)
    if match:
        candidates.append(match.group(1))
    meta = _META_CHARSET.search(content[:2048])
    if meta:
        candidates.append(meta.group(1).decode("ascii", "ignore"))
    candidates.append("utf-8")
    for encoding in candidates:
        try:
            return content.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return content.decode("utf-8", errors="replace")


def _should_read(content_type: str) -> bool:
    content_type = content_type.lower()
    return any(content_type.startswith(t) for t in _TEXT_TYPES) or content_type == ""


async def fetch(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
    max_bytes: int = DEFAULT_MAX_BYTES,
    read_any: bool = False,
) -> FetchResult:
    """GET ``url``, following redirects by hand so every hop is recorded.

    The body is read only for text-like content types (HTML, XML, plain text),
    or for any type when ``read_any`` is set, and never beyond ``max_bytes``.
    Network errors are returned in ``error`` instead of being raised.
    """
    hops: list[Hop] = []
    seen = {url}
    current = url
    started = time.perf_counter()
    while True:
        try:
            async with client.stream("GET", current) as response:
                elapsed_ms = (time.perf_counter() - started) * 1000
                location = response.headers.get("location")
                if response.status_code in REDIRECT_STATUSES and location:
                    hops.append(Hop(url=current, status=response.status_code))
                    target = normalize_url(location, base=current)
                    redirect_error: str | None = None
                    if target is None:
                        redirect_error = f"redirect to an unsupported URL: {location}"
                    elif target in seen:
                        redirect_error = "redirect loop"
                    elif len(hops) >= max_redirects:
                        redirect_error = "too many redirects"
                    if redirect_error is not None or target is None:
                        return FetchResult(
                            url=url,
                            final_url=target or current,
                            redirects=hops,
                            headers=response.headers,
                            response_ms=elapsed_ms,
                            error=redirect_error,
                        )
                    seen.add(target)
                    current = target
                    continue

                content = b""
                truncated = False
                if read_any or _should_read(response.headers.get("content-type", "")):
                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in response.aiter_bytes():
                        chunks.append(chunk)
                        total += len(chunk)
                        if total > max_bytes:
                            truncated = True
                            break
                    content = b"".join(chunks)[:max_bytes]
                size = len(content)
                declared = response.headers.get("content-length")
                if declared and declared.isdigit() and not content:
                    size = int(declared)
                return FetchResult(
                    url=url,
                    final_url=current,
                    status=response.status_code,
                    redirects=hops,
                    headers=response.headers,
                    content=content,
                    response_ms=elapsed_ms,
                    size=size,
                    truncated=truncated,
                )
        except httpx.TimeoutException:
            error = "timeout"
        except (httpx.HTTPError, httpx.InvalidURL) as exc:
            error = f"{type(exc).__name__}: {exc}".rstrip(": ")
        return FetchResult(
            url=url,
            final_url=current,
            redirects=hops,
            response_ms=(time.perf_counter() - started) * 1000,
            error=error,
        )
