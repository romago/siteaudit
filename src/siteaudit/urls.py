"""URL helpers: normalization and same-site checks."""

from urllib.parse import urljoin, urlsplit, urlunsplit

_DEFAULT_PORTS = {"http": 80, "https": 443}


def normalize_url(url: str, base: str | None = None) -> str | None:
    """Return a canonical form of ``url`` for de-duplication, or None if it is not http(s).

    Resolves against ``base``, drops the fragment, lowercases scheme and host,
    removes the default port and turns an empty path into ``/``. The query is kept.
    """
    url = url.strip()
    if not url:
        return None
    if base is not None:
        url = urljoin(base, url)
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return None
    scheme = parts.scheme.lower()
    if scheme not in _DEFAULT_PORTS or not parts.hostname:
        return None
    host = parts.hostname.lower().rstrip(".")
    if ":" in host:  # IPv6 literal
        host = f"[{host}]"
    netloc = host if port in (None, _DEFAULT_PORTS[scheme]) else f"{host}:{port}"
    path = parts.path or "/"
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def site_key(host: str) -> str:
    """Host without a leading ``www.``, so example.com and www.example.com count as one site."""
    host = host.lower()
    return host[4:] if host.startswith("www.") else host


def is_internal(url: str, site_host: str) -> bool:
    return site_key(host_of(url)) == site_key(site_host)


def origin_of(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"
