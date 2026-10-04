"""
Playwright dynamic browser renderer implementation matching Phase 4 & Section 10 of Implementation Plan.
Implements the Renderer interface protocol with resource cleanup and bounded concurrency.
"""
import asyncio
from typing import Optional
from project.config.settings import CrawlConfig
from project.interfaces.renderer import Renderer
from project.schemas.result_schema import RetrievalResult, ProcessingError
from project.utils.logging import logger
from project.utils.exceptions import RenderingError


class PlaywrightRenderer(Renderer):
    """
    Dynamic browser rendering service using Playwright async API.
    Used exclusively as a fallback for JavaScript-rendered SPAs when static retrieval is insufficient.
    """

    def __init__(self, max_browser_concurrency: int = 2):
        self._semaphore = asyncio.Semaphore(max_browser_concurrency)
        self._playwright = None
        self._browser = None
        self._lock = asyncio.Lock()

    async def _ensure_browser(self):
        """Lazily initializes the Playwright browser runtime."""
        async with self._lock:
            if self._browser is None:
                try:
                    from playwright.async_api import async_playwright
                    self._playwright = await async_playwright().start()
                    self._browser = await self._playwright.chromium.launch(
                        headless=True,
                        args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
                    )
                    logger.info("Playwright headless Chromium browser initialized.")
                except Exception as exc:
                    logger.error(f"Failed to initialize Playwright browser: {exc}")
                    raise RenderingError(f"Could not launch browser: {exc}") from exc

    async def render(self, url: str, config: CrawlConfig) -> RetrievalResult:
        """
        Renders the target webpage in a headless browser and returns the fully evaluated DOM HTML.
        Guarantees deterministic resource cleanup for pages and contexts.
        """
        if not (url.startswith("http://") or url.startswith("https://")):
            return RetrievalResult(
                url=url,
                success=False,
                is_rendered=True,
                error=ProcessingError(
                    category="URL_VALIDATION_ERROR",
                    message=f"Unsupported URL scheme: {url}",
                    attempt=1,
                    recoverable=False,
                ),
            )

        async with self._semaphore:
            try:
                await self._ensure_browser()
            except Exception as exc:
                return RetrievalResult(
                    url=url,
                    success=False,
                    is_rendered=True,
                    error=ProcessingError(
                        category="JS_RENDERING_ERROR",
                        message=str(exc),
                        attempt=1,
                        recoverable=False,
                    ),
                )

            context = None
            page = None
            try:
                timeout_ms = config.timeout_seconds * 1000
                context = await self._browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                               "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 WebDataAcq/1.0"
                )
                page = await context.new_page()
                page.set_default_timeout(timeout_ms)

                response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                # Wait briefly for client-side frameworks (React, Vue, Angular) to mount
                try:
                    await page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 5000))
                except Exception:
                    # Non-fatal if networkidle times out
                    pass

                content = await page.content()
                status_code = response.status if response else 200

                return RetrievalResult(
                    url=page.url,
                    status_code=status_code,
                    content=content,
                    content_type="text/html; charset=utf-8",
                    success=True,
                    is_rendered=True,
                    error=None,
                )
            except Exception as exc:
                logger.error(f"Playwright rendering failed for {url}: {exc}")
                return RetrievalResult(
                    url=url,
                    success=False,
                    is_rendered=True,
                    error=ProcessingError(
                        category="JS_RENDERING_ERROR",
                        message=f"Playwright error: {str(exc)}",
                        attempt=1,
                        recoverable=False,
                    ),
                )
            finally:
                if page:
                    try:
                        await page.close()
                    except Exception:
                        pass
                if context:
                    try:
                        await context.close()
                    except Exception:
                        pass

    async def close(self) -> None:
        """Cleans up the Playwright browser process and context."""
        async with self._lock:
            if self._browser:
                try:
                    await self._browser.close()
                except Exception:
                    pass
                self._browser = None
            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None
            logger.info("Playwright browser runtime terminated.")
