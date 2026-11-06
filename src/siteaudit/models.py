"""Result models shared by the crawler, the checks and the reports."""

from pydantic import BaseModel, Field


class Hop(BaseModel):
    """One redirect response: the URL that was requested and the status it returned."""

    url: str
    status: int


class Hreflang(BaseModel):
    lang: str
    href: str


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
    found_via: list[str] = Field(default_factory=list)

    links: list[str] = Field(default_factory=list)
    """Internal ``<a href>`` targets, normalized and de-duplicated."""
    external_links: int = 0
    canonical: str | None = None
    hreflang: list[Hreflang] = Field(default_factory=list)

    @property
    def is_html(self) -> bool:
        return self.content_type in ("text/html", "application/xhtml+xml")

    @property
    def ok(self) -> bool:
        return self.status is not None and 200 <= self.status < 300
