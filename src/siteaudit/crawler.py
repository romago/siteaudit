"""Async breadth-first crawl of one site: robots.txt, sitemaps, then internal links."""

import asyncio
from collections import deque
from dataclasses import dataclass, field, replace

import httpx

from siteaudit import USER_AGENT
from siteaudit.fetch import DEFAULT_MAX_BYTES, FetchResult, fetch
from siteaudit.models import Page
from siteaudit.parse import parse_page
from siteaudit.robots import RobotsTxt
from siteaudit.sitemap import SitemapError, parse_sitemap
from siteaudit.urls import host_of, is_internal, normalize_url, origin_of

ROBOTS_AGENT = "siteaudit"
MAX_SITEMAP_FILES = 50


@dataclass(slots=True)
class CrawlOptions:
    max_pages: int = 500
    concurrency: int = 5
    timeout: float = 15.0
    max_bytes: int = DEFAULT_MAX_BYTES
    user_agent: str = USER_AGENT
    respect_robots: bool = True
    use_sitemaps: bool = True


@dataclass(slots=True)
class SitemapFetch:
    url: str
    status: int | None
    error: str | None = None
    url_count: int = 0
    is_index: bool = False


@dataclass(slots=True)
class CrawlResult:
    start_url: str
    site_host: str
    robots_url: str = ""
    robots_status: int | None = None
    robots: RobotsTxt | None = None
    sitemaps: list[SitemapFetch] = field(default_factory=list)
    sitemap_urls: list[str] = field(default_factory=list)
    pages: dict[str, Page] = field(default_factory=dict)
    inlinks: dict[str, set[str]] = field(default_factory=dict)
    """Internal link target -> pages that link to it with ``<a href>``."""
    blocked: dict[str, set[str]] = field(default_factory=dict)
    """URLs not crawled because robots.txt disallows them -> where they were found."""
    limit_reached: bool = False


class Crawler:
    def __init__(self, start_url: str, options: CrawlOptions | None = None) -> None:
        normalized = normalize_url(start_url)
        if normalized is None:
            raise ValueError(f"not an http(s) URL: {start_url!r}")
        self.options = options or CrawlOptions()
        self.result = CrawlResult(start_url=normalized, site_host=host_of(normalized))
        self._seen: set[str] = set()
        self._queue: deque[str] = deque()
        self._sitemap_queue: deque[str] = deque()
        self._found_via: dict[str, list[str]] = {}

    async def run(self) -> CrawlResult:
        opts = self.options
        async with httpx.AsyncClient(
            headers={"User-Agent": opts.user_agent},
            timeout=opts.timeout,
            follow_redirects=False,
            limits=httpx.Limits(max_connections=opts.concurrency),
        ) as client:
            start = self.result.start_url
            self._mark(start, "start")
            first = await fetch(client, start, max_bytes=opts.max_bytes)
            if first.final_url and is_internal(first.final_url, self.result.site_host):
                # Adopt the host the site redirects to (http -> https, apex -> www).
                self.result.site_host = host_of(first.final_url)
            await self._load_robots(client, origin_of(first.final_url or start))
            if opts.use_sitemaps:
                await self._load_sitemaps(client, origin_of(first.final_url or start))
            self._record(first)
            await self._crawl(client, budget=opts.max_pages - 1)
        return self.result

    # -- discovery ---------------------------------------------------------

    def _mark(self, url: str, via: str) -> None:
        vias = self._found_via.setdefault(url, [])
        if via not in vias:
            vias.append(via)
        page = self.result.pages.get(url)
        if page is not None and via not in page.found_via:
            page.found_via.append(via)

    def _allowed(self, url: str) -> bool:
        robots = self.result.robots
        if not self.options.respect_robots or robots is None:
            return True
        return robots.can_fetch(url, ROBOTS_AGENT)

    def _discover(self, url: str, via: str, referrer: str, *, sitemap: bool = False) -> None:
        if not is_internal(url, self.result.site_host):
            return
        self._mark(url, via)
        if url in self._seen:
            return
        if not self._allowed(url):
            self.result.blocked.setdefault(url, set()).add(referrer)
            return
        self._seen.add(url)
        (self._sitemap_queue if sitemap else self._queue).append(url)

    def _record(self, result: FetchResult) -> None:
        self._seen.add(result.url)
        host = self.result.site_host
        if not result.redirects:
            page = parse_page(result, host, self._found_via.get(result.url))
            self.result.pages[result.url] = page
            self._follow(page)
            return
        # A redirecting URL keeps its status and chain but has no content of its own.
        self.result.pages[result.url] = parse_page(
            replace(result, content=b""), host, self._found_via.get(result.url)
        )
        target = result.final_url
        if not result.ok or not is_internal(target, host):
            return
        # The target was fetched as part of this request: record it as its own page,
        # so it is not fetched again and its links are followed.
        self._mark(target, "redirect")
        if target in self.result.pages:
            return
        self._seen.add(target)
        landed = replace(result, url=target, redirects=[])
        target_page = parse_page(landed, host, self._found_via.get(target))
        self.result.pages[target] = target_page
        self._follow(target_page)

    def _follow(self, page: Page) -> None:
        for link in page.links:
            self.result.inlinks.setdefault(link, set()).add(page.url)
            self._discover(link, "link", page.url)
        if page.canonical:
            self._discover(page.canonical, "canonical", page.url)
        for alt in page.hreflang:
            self._discover(alt.href, "hreflang", page.url)

    # -- robots.txt and sitemaps ------------------------------------------

    async def _load_robots(self, client: httpx.AsyncClient, origin: str) -> None:
        url = f"{origin}/robots.txt"
        self.result.robots_url = url
        response = await fetch(client, url, max_bytes=512 * 1024, read_any=True)
        self.result.robots_status = response.status
        if response.status == 200:
            self.result.robots = RobotsTxt.parse(response.text)

    async def _load_sitemaps(self, client: httpx.AsyncClient, origin: str) -> None:
        robots = self.result.robots
        declared = robots.sitemaps if robots and robots.sitemaps else [f"{origin}/sitemap.xml"]
        pending = deque(u for u in (normalize_url(s) for s in declared) if u)
        visited: set[str] = set()
        found: dict[str, None] = {}
        while pending and len(visited) < MAX_SITEMAP_FILES:
            url = pending.popleft()
            if url in visited:
                continue
            visited.add(url)
            response = await fetch(client, url, max_bytes=self.options.max_bytes, read_any=True)
            entry = SitemapFetch(url=url, status=response.status, error=response.error)
            self.result.sitemaps.append(entry)
            if not response.ok:
                continue
            try:
                doc = parse_sitemap(response.content)
            except SitemapError as exc:
                entry.error = str(exc)
                continue
            entry.is_index = bool(doc.children)
            entry.url_count = len(doc.urls) or len(doc.children)
            pending.extend(u for u in (normalize_url(c) for c in doc.children) if u)
            for loc in doc.urls:
                normalized = normalize_url(loc)
                if normalized:
                    found.setdefault(normalized, None)
        self.result.sitemap_urls = list(found)
        for url in self.result.sitemap_urls:
            self._discover(url, "sitemap", "sitemap.xml", sitemap=True)

    # -- the crawl loop ----------------------------------------------------

    def _next_url(self) -> str | None:
        if self._queue:
            return self._queue.popleft()
        if self._sitemap_queue:
            return self._sitemap_queue.popleft()
        return None

    async def _crawl(self, client: httpx.AsyncClient, budget: int) -> None:
        opts = self.options
        pending: set[asyncio.Task[FetchResult]] = set()
        while True:
            while budget > 0 and len(pending) < opts.concurrency:
                url = self._next_url()
                if url is None:
                    break
                if url in self.result.pages:  # recorded as a redirect target meanwhile
                    continue
                budget -= 1
                pending.add(asyncio.create_task(fetch(client, url, max_bytes=opts.max_bytes)))
            if not pending:
                break
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                self._record(task.result())
        self.result.limit_reached = bool(self._queue or self._sitemap_queue)


async def crawl(start_url: str, options: CrawlOptions | None = None) -> CrawlResult:
    return await Crawler(start_url, options).run()
