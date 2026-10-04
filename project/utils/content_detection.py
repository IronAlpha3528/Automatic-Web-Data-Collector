"""
Content sufficiency detection utility matching Phase 4 & Section 10 of Implementation Plan.
Determines whether statically retrieved HTML requires Playwright JavaScript rendering.
"""
import re
from typing import Union, Optional
from bs4 import BeautifulSoup


# Common SPA root containers that indicate client-side rendering
SPA_ROOT_PATTERNS = [
    re.compile(r'<div[^>]+id=["\'](?:root|app|__next|__nuxt|main-app)["\'][^>]*>\s*</div>', re.IGNORECASE),
    re.compile(r'<noscript>[^<]*(?:enable javascript|requires javascript|javascript must be enabled)[^<]*</noscript>', re.IGNORECASE),
]

MIN_BODY_TEXT_LENGTH = 80


def needs_javascript_rendering(
    content: Optional[Union[str, bytes]],
    content_type: Optional[str] = None,
) -> bool:
    """
    Evaluates whether HTML content is insufficient and requires dynamic JavaScript rendering.
    
    Args:
        content: The retrieved response body (string or bytes).
        content_type: MIME type header from HTTP response.

    Returns:
        True if the content appears to be a client-rendered SPA or lacks body text, False otherwise.
    """
    if content is None:
        return True

    # Do not invoke JS rendering for PDF or binary assets
    if content_type:
        ct = content_type.lower()
        if "application/pdf" in ct or "image/" in ct or "application/octet-stream" in ct:
            return False

    if isinstance(content, bytes):
        try:
            html = content.decode("utf-8", errors="replace")
        except Exception:
            return False
    else:
        html = content

    # 1. Check for empty or whitespace-only response
    trimmed = html.strip()
    if not trimmed:
        return True

    # 2. Check for characteristic SPA placeholder patterns
    for pattern in SPA_ROOT_PATTERNS:
        if pattern.search(html):
            return True

    # 3. Quick structural evaluation via BeautifulSoup
    try:
        soup = BeautifulSoup(html, "html.parser")
        body = soup.find("body")
        if not body:
            return True

        # Extract text excluding scripts and styles
        for element in body(["script", "style", "noscript", "template"]):
            element.extract()

        visible_text = body.get_text(separator=" ", strip=True)
        if len(visible_text) < MIN_BODY_TEXT_LENGTH:
            # Check if there are script tags suggesting an SPA bundle
            has_scripts = bool(soup.find_all("script"))
            if has_scripts:
                return True
    except Exception:
        # If parsing fails or causes issues, do not force JS rendering
        pass

    return False
