"""siteaudit: crawl a website and write an SEO and technical audit report."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("site-audit")
except PackageNotFoundError:  # pragma: no cover - running from a source tree without install
    __version__ = "0.0.0"

USER_AGENT = f"siteaudit/{__version__} (+https://github.com/romago/siteaudit)"

__all__ = ["USER_AGENT", "__version__"]
