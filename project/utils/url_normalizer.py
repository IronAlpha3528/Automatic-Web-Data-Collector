"""
URL validation and normalization module matching Section 7 of Implementation Plan.
Standardizes URLs deterministically to prevent duplicate crawling and loops.
"""
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
import posixpath
import re

SUPPORTED_SCHEMES = {"http", "https"}


def is_valid_url(url: str) -> bool:
    """
    Validates whether a URL has a supported HTTP/HTTPS scheme and valid network location.
    Rejects ftp://, file://, javascript:, data:, and malformed inputs.
    """
    if not url or not isinstance(url, str):
        return False

    url_str = url.strip()
    if not url_str:
        return False

    try:
        parsed = urlparse(url_str)
        if parsed.scheme.lower() not in SUPPORTED_SCHEMES:
            return False
        if not parsed.netloc:
            return False
        return True
    except Exception:
        return False


def normalize_url(url: str) -> str:
    """
    Normalizes a URL string deterministically according to Section 7 rules:
    - Lowercase scheme and hostname
    - Remove default ports (80 for http, 443 for https)
    - Remove fragment identifiers (#...)
    - Normalize path slashes and relative components
    - Sort query parameters alphabetically for deterministic comparison
    - Conservative path cleanup without losing semantic parameters

    Args:
        url: Raw URL string.

    Returns:
        Normalized URL string.

    Raises:
        ValueError: If the URL is invalid or has an unsupported scheme.
    """
    if not is_valid_url(url):
        raise ValueError(f"Invalid or unsupported URL for normalization: '{url}'")

    parsed = urlparse(url.strip())

    # 1. Lowercase scheme
    scheme = parsed.scheme.lower()

    # 2. Lowercase hostname and handle default ports
    netloc = parsed.netloc.lower()
    if ":" in netloc:
        host, port = netloc.rsplit(":", 1)
        if (scheme == "http" and port == "80") or (scheme == "https" and port == "443"):
            netloc = host

    # 3. Path normalization
    path = parsed.path
    if not path:
        path = "/"
    else:
        # Collapse multiple consecutive slashes
        path = re.sub(r"/+", "/", path)
        # Resolve ./ and ../ in paths cleanly
        segments = path.split("/")
        resolved_segments = []
        for seg in segments:
            if seg == "..":
                if resolved_segments and resolved_segments[-1] != "":
                    resolved_segments.pop()
            elif seg != ".":
                resolved_segments.append(seg)
        path = "/".join(resolved_segments) or "/"

    # 4. Deterministic query parameter sorting
    query = ""
    if parsed.query:
        params = parse_qsl(parsed.query, keep_blank_values=True)
        # Sort by parameter key then value for deterministic URL hashing
        params.sort(key=lambda x: (x[0], x[1]))
        query = urlencode(params)

    # 5. Drop fragments entirely
    fragment = ""

    normalized = urlunparse((scheme, netloc, path, "", query, fragment))
    return normalized
