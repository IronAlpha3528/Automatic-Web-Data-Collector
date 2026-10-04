"""
HTTPX primary retriever implementation matching Phase 3 & Section 10 of Implementation Plan.
Implements the Retriever interface protocol with bounded retries, timeouts, and domain rate limiting.
"""
from typing import Optional
import httpx
from project.config.settings import CrawlConfig
from project.interfaces.retriever import Retriever
from project.schemas.result_schema import RetrievalResult, ProcessingError
from project.utils.logging import logger
from project.utils.rate_limiter import DomainRateLimiter
from project.utils.retry import execute_with_retry, is_retryable_status_code
from project.utils.exceptions import TimeoutError, NetworkError, HTTPError


class HTTPXRetriever(Retriever):
    """
    Primary HTTP/HTTPS retrieval service using httpx.AsyncClient.
    Provides isolated failure handling, status classification, bounded retries, and pacing.
    """

    def __init__(
        self,
        rate_limiter: Optional[DomainRateLimiter] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.rate_limiter = rate_limiter or DomainRateLimiter()
        self._custom_client = client

    async def _fetch(
        self,
        url: str,
        client: httpx.AsyncClient,
        timeout: float,
        attempt: int,
    ) -> httpx.Response:
        """Internal fetch function invoked by the retry executor."""
        try:
            response = await client.get(url, timeout=timeout, follow_redirects=True)
            # Check for 5xx or 429 to raise HTTPError for retry mechanism
            if is_retryable_status_code(response.status_code):
                raise HTTPError(
                    f"Server returned retryable status {response.status_code}",
                    status_code=response.status_code,
                )
            return response
        except httpx.TimeoutException as exc:
            raise TimeoutError(f"HTTPX timeout after {timeout}s: {exc}") from exc
        except (httpx.NetworkError, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            raise NetworkError(f"HTTPX network error connecting to {url}: {exc}") from exc

    async def retrieve(self, url: str, config: CrawlConfig) -> RetrievalResult:
        """
        Fetches the webpage or binary asset at url according to config.
        Guarantees URL-level failure isolation by returning a controlled RetrievalResult.
        """
        # Validate URL scheme
        if not (url.startswith("http://") or url.startswith("https://")):
            return RetrievalResult(
                url=url,
                success=False,
                error=ProcessingError(
                    category="URL_VALIDATION_ERROR",
                    message=f"Unsupported URL scheme: {url}",
                    attempt=1,
                    recoverable=False,
                ),
            )

        # 1. Apply domain rate limiter
        await self.rate_limiter.acquire(url, rate_limit=config.domain_rate_limit)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 WebDataAcq/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        async def _do_retrieve(attempt: int) -> RetrievalResult:
            if self._custom_client:
                resp = await self._fetch(url, self._custom_client, float(config.timeout_seconds), attempt)
            else:
                async with httpx.AsyncClient(headers=headers, verify=False) as client:
                    resp = await self._fetch(url, client, float(config.timeout_seconds), attempt)

            content_type = resp.headers.get("content-type", "").lower()
            
            # Check for non-retryable 4xx client errors
            if 400 <= resp.status_code < 500:
                logger.warning(f"HTTP client error {resp.status_code} for {url}")
                return RetrievalResult(
                    url=str(resp.url),
                    status_code=resp.status_code,
                    content_type=content_type,
                    success=False,
                    error=ProcessingError(
                        category="HTTP_ERROR",
                        message=f"Client error HTTP {resp.status_code}",
                        attempt=attempt,
                        recoverable=False,
                    ),
                )

            # Determine whether content is binary (PDF, image) or text (HTML, XML, plaintext)
            if "application/pdf" in content_type or "image/" in content_type:
                content = resp.content  # bytes
            else:
                content = resp.text     # decoded str

            return RetrievalResult(
                url=str(resp.url),
                status_code=resp.status_code,
                content=content,
                content_type=content_type,
                success=True,
                is_rendered=False,
                error=None,
            )

        try:
            return await execute_with_retry(
                _do_retrieve,
                max_retries=config.max_retries,
                base_delay=1.0,
            )
        except TimeoutError as exc:
            logger.error(f"Final timeout error retrieving {url}: {exc}")
            return RetrievalResult(
                url=url,
                success=False,
                error=ProcessingError(
                    category="TIMEOUT_ERROR",
                    message=str(exc),
                    attempt=config.max_retries + 1,
                    recoverable=False,
                ),
            )
        except NetworkError as exc:
            logger.error(f"Final network error retrieving {url}: {exc}")
            return RetrievalResult(
                url=url,
                success=False,
                error=ProcessingError(
                    category="NETWORK_ERROR",
                    message=str(exc),
                    attempt=config.max_retries + 1,
                    recoverable=False,
                ),
            )
        except HTTPError as exc:
            logger.error(f"Final HTTP error retrieving {url}: {exc}")
            return RetrievalResult(
                url=url,
                status_code=exc.status_code,
                success=False,
                error=ProcessingError(
                    category="HTTP_ERROR",
                    message=str(exc),
                    attempt=config.max_retries + 1,
                    recoverable=False,
                ),
            )
        except Exception as exc:
            logger.error(f"Unexpected error retrieving {url}: {exc}")
            return RetrievalResult(
                url=url,
                success=False,
                error=ProcessingError(
                    category="NETWORK_ERROR",
                    message=f"Unexpected retrieval failure: {exc}",
                    attempt=1,
                    recoverable=False,
                ),
            )
