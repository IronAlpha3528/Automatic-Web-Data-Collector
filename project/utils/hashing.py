"""
Content hashing module matching Section 25 of Implementation Plan.
Provides deterministic SHA-256 content hashing for deduplication metadata.
"""
import hashlib


def compute_content_hash(content: str) -> str:
    """
    Computes a deterministic SHA-256 hash of normalized text content.

    Args:
        content: Cleaned and normalized text content string.

    Returns:
        Hexadecimal SHA-256 digest string.
    """
    if content is None:
        content = ""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
