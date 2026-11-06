"""sitemap.xml and sitemap index parsing."""

import gzip
import io
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

MAX_DECOMPRESSED_BYTES = 50 * 1024 * 1024  # the sitemap protocol limit


class SitemapError(ValueError):
    """The document is not a readable sitemap."""


@dataclass(slots=True)
class SitemapDocument:
    urls: list[str] = field(default_factory=list)
    """Page URLs from a ``<urlset>``."""
    children: list[str] = field(default_factory=list)
    """Sitemap URLs from a ``<sitemapindex>``."""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_sitemap(content: bytes) -> SitemapDocument:
    """Parse a ``<urlset>`` or ``<sitemapindex>`` document, gzipped or not."""
    if content[:2] == b"\x1f\x8b":
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(content)) as fh:
                content = fh.read(MAX_DECOMPRESSED_BYTES + 1)
        except OSError as exc:
            raise SitemapError(f"bad gzip data: {exc}") from exc
        if len(content) > MAX_DECOMPRESSED_BYTES:
            raise SitemapError("sitemap is larger than 50 MB")
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise SitemapError(f"invalid XML: {exc}") from exc

    kind = _local(root.tag)
    if kind not in ("urlset", "sitemapindex"):
        raise SitemapError(f"unexpected root element <{kind}>")
    entry = "url" if kind == "urlset" else "sitemap"
    locs: list[str] = []
    for item in root:
        if _local(item.tag) != entry:
            continue
        for child in item:
            if _local(child.tag) == "loc" and child.text and child.text.strip():
                locs.append(child.text.strip())
                break
    if kind == "urlset":
        return SitemapDocument(urls=locs)
    return SitemapDocument(children=locs)
