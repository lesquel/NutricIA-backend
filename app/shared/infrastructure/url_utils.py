"""Shared URL utilities — build absolute image URLs from relative paths."""

from urllib.parse import urlparse


def to_relative_path(url_or_path: str | None) -> str | None:
    """Strip any host prefix, returning just the path component.

    Already-relative paths pass through unchanged.  ``None`` stays ``None``.
    """
    if url_or_path is None:
        return None
    if url_or_path == "":
        return ""
    if url_or_path.startswith(("http://", "https://")):
        return urlparse(url_or_path).path
    return url_or_path


def resolve_image_url(path_or_url: str | None, base_url: str) -> str | None:
    """Resolve a stored path to an absolute URL using *base_url*.

    Handles:
    * ``None`` / empty → ``None``
    * Relative path (``/uploads/...``) → ``{base_url}/uploads/...``
    * Legacy absolute URL already in DB → strips old host and re-resolves
    """
    if not path_or_url:
        return None
    relative = to_relative_path(path_or_url)
    if not relative:
        return None
    base = str(base_url).rstrip("/")
    if not relative.startswith("/"):
        relative = f"/{relative}"
    return f"{base}{relative}"
