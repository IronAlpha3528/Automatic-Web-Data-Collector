"""
Domain-specific rate limiting module matching Section 19 of Implementation Plan.
Centralizes asynchronous request pacing per domain to prevent server overload.
"""
import asyncio
import time
from urllib.parse import urlparse
from typing import Dict
from project.utils.logging import logger


class DomainRateLimiter:
    """
    Thread-safe asynchronous rate limiter that enforces per-domain request pacing.
    """

    def __init__(self, default_rate_limit: float = 2.0):
        """
        Args:
            default_rate_limit: Default requests per second per domain.
        """
        self.default_rate_limit = default_rate_limit
        self._last_request_time: Dict[str, float] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    def _extract_domain(self, url: str) -> str:
        """Extracts normalized hostname/netloc from URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            return domain if domain else "default"
        except Exception:
            return "default"

    async def _get_domain_lock(self, domain: str) -> asyncio.Lock:
        """Retrieves or creates a dedicated async lock for a domain."""
        async with self._global_lock:
            if domain not in self._locks:
                self._locks[domain] = asyncio.Lock()
            return self._locks[domain]

    async def acquire(self, url: str, rate_limit: float = None) -> None:
        """
        Enforces rate limiting delay before proceeding with request for given URL.
        
        Args:
            url: Target URL whose domain will be rate limited.
            rate_limit: Requests per second for this domain (defaults to self.default_rate_limit).
        """
        domain = self._extract_domain(url)
        limit = rate_limit if (rate_limit is not None and rate_limit > 0) else self.default_rate_limit
        min_interval = 1.0 / limit

        domain_lock = await self._get_domain_lock(domain)
        async with domain_lock:
            now = time.monotonic()
            last_time = self._last_request_time.get(domain, 0.0)
            elapsed = now - last_time

            if elapsed < min_interval:
                sleep_needed = min_interval - elapsed
                logger.debug(
                    f"Rate limiting domain '{domain}': sleeping for {sleep_needed:.3f}s"
                )
                await asyncio.sleep(sleep_needed)

            self._last_request_time[domain] = time.monotonic()

    def reset(self) -> None:
        """Resets all domain timestamps and tracking state."""
        self._last_request_time.clear()
        self._locks.clear()
