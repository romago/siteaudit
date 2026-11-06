"""Result models shared by the crawler, the checks and the reports."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    NOTICE = "notice"

    @property
    def rank(self) -> int:
        return {"error": 0, "warning": 1, "notice": 2}[self.value]


class Hop(BaseModel):
    """One redirect response: the URL that was requested and the status it returned."""

    url: str
    status: int


class Hreflang(BaseModel):
    lang: str
    href: str


class JsonLd(BaseModel):
    """One ``<script type="application/ld+json">`` block."""

    valid: bool
    types: list[str] = Field(default_factory=list)
    error: str | None = None


class Page(BaseModel):
    """Everything siteaudit knows about one crawled URL."""

    url: str
    final_url: str
    status: int | None = None
    redirects: list[Hop] = Field(default_factory=list)
    error: str | None = None
    content_type: str = ""
    response_ms: float = 0.0
    size: int = 0
    truncated: bool = False
    found_via: list[str] = Field(default_factory=list)

    title: str | None = None
    title_count: int = 0
    description: str | None = None
    description_count: int = 0
    h1: list[str] = Field(default_factory=list)
    lang: str | None = None
    viewport: bool = False
    canonical: str | None = None
    canonical_count: int = 0
    meta_robots: str | None = None
    x_robots_tag: str | None = None
    hreflang: list[Hreflang] = Field(default_factory=list)
    json_ld: list[JsonLd] = Field(default_factory=list)
    image_count: int = 0
    images_without_alt: list[str] = Field(default_factory=list)

    links: list[str] = Field(default_factory=list)
    """Internal ``<a href>`` targets, normalized and de-duplicated."""
    external_links: int = 0

    @property
    def is_html(self) -> bool:
        return self.content_type in ("text/html", "application/xhtml+xml")

    @property
    def ok(self) -> bool:
        return self.status is not None and 200 <= self.status < 300

    @property
    def is_redirect(self) -> bool:
        return bool(self.redirects)

    @property
    def is_indexable_html(self) -> bool:
        """A 2xx HTML response that was served at this URL, not after a redirect."""
        return self.ok and self.is_html and not self.redirects

    @property
    def robots_directives(self) -> set[str]:
        """Directives from meta robots and X-Robots-Tag that apply to all crawlers."""
        directives: set[str] = set()
        for source in (self.meta_robots, self.x_robots_tag):
            for part in (source or "").lower().split(","):
                token = part.strip()
                if ":" in token:  # "googlebot: noindex" names one crawler; keep the rule
                    token = token.split(":", 1)[1].strip()
                if token:
                    directives.add(token)
        return directives

    @property
    def noindex(self) -> bool:
        return bool({"noindex", "none"} & self.robots_directives)

    @property
    def nofollow(self) -> bool:
        return bool({"nofollow", "none"} & self.robots_directives)


class Issue(BaseModel):
    code: str
    severity: Severity
    url: str
    message: str
    related: list[str] = Field(default_factory=list)
    """Other URLs that explain the issue: referrers, redirect hops, image sources."""


class AuditResult(BaseModel):
    start_url: str
    site_host: str
    started_at: datetime
    duration_s: float
    pages: list[Page]
    issues: list[Issue]
    sitemap_urls: list[str] = Field(default_factory=list)
    robots_url: str = ""
    robots_status: int | None = None
    limit_reached: bool = False
