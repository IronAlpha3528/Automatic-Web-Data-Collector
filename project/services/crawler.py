"""
Crawler service executing Breadth-First Search (BFS) link traversal and content pipeline.
Adheres to Section 44 (Crawler Contract) and Section 45 (URL Processing Algorithm).
"""
import asyncio
import urllib.robotparser
from urllib.parse import urlparse
from typing import Optional, List, Dict
from project.schemas.result_schema import ProcessingError
from project.config.settings import CrawlConfig
from project.schemas.url_schema import CrawlURL
from project.schemas.page_schema import ProcessedDocument
from project.schemas.result_schema import URLProcessingResult
from project.interfaces.retriever import Retriever
from project.interfaces.renderer import Renderer
from project.interfaces.parser import Parser
from project.interfaces.extractor import Extractor
from project.interfaces.storage import Storage
from project.interfaces.media import MediaDownloader
from project.services.url_manager import URLManager
from project.services.retriever import HTTPXRetriever
from project.services.parser import DocumentParser
from project.services.extractor import ContentExtractor
from project.services.preprocessor import ContentPreprocessor
from project.services.media_downloader import DefaultMediaDownloader
from project.services.error_manager import ErrorManager
from project.utils.content_detection import needs_javascript_rendering
from project.utils.logging import logger

class Crawler:
    """
    Decoupled BFS crawl engine executing the 16-step processing pipeline per URL.
    Coordinates URLManager, Retriever, Renderer, Parser, Extractor, Preprocessor, and Storage.
    """

    def __init__(
        self,
        retriever: Optional[Retriever] = None,
        renderer: Optional[Renderer] = None,
        parser: Optional[Parser] = None,
        extractor: Optional[Extractor] = None,
        preprocessor: Optional[ContentPreprocessor] = None,
        media_downloader: Optional[MediaDownloader] = None,
        storage: Optional[Storage] = None,
        error_manager: Optional[ErrorManager] = None,
    ):
        self.retriever = retriever or HTTPXRetriever()
        self.renderer = renderer
        self.parser = parser or DocumentParser()
        self.extractor = extractor or ContentExtractor()
        self.preprocessor = preprocessor or ContentPreprocessor()
        self.media_downloader = media_downloader or DefaultMediaDownloader()
        self.storage = storage
        self.error_manager = error_manager or ErrorManager(storage=storage)
        self._robots_cache: Dict[str, urllib.robotparser.RobotFileParser] = {}

    async def _is_allowed_by_robots(self, url: str) -> bool:
        """Checks if URL is permitted by robots.txt under respect policy."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if not domain:
                return True
            if domain not in self._robots_cache:
                rp = urllib.robotparser.RobotFileParser()
                robots_url = f"{parsed.scheme}://{domain}/robots.txt"
                try:
                    retrieval = await self.retriever.retrieve(robots_url, CrawlConfig(timeout_seconds=5, max_retries=1))
                    if retrieval.success and isinstance(retrieval.content, str):
                        rp.parse(retrieval.content.splitlines())
                    else:
                        rp.allow_all = True
                except Exception:
                    rp.allow_all = True
                self._robots_cache[domain] = rp

            rp = self._robots_cache[domain]
            return rp.can_fetch("WebDataAcquisitionBot", url) or rp.can_fetch("*", url)
        except Exception:
            return True

    async def process_url(
        self,
        crawl_item: CrawlURL,
        config: CrawlConfig,
        job_id: str,
    ) -> URLProcessingResult:
        """
        Executes Section 45 16-step pipeline on a single URL with failure isolation.
        """
        raw_url = crawl_item.url
        normalized = crawl_item.normalized_url

        # Check robots.txt policy if set to respect
        if config.robots_mode == "respect":
            allowed = await self._is_allowed_by_robots(raw_url)
            if not allowed:
                logger.info(f"URL disallowed by robots.txt: {raw_url}")
                if self.storage:
                    await self.storage.update_url_status(job_id, normalized, "SKIPPED")
                    await self.storage.update_job_counters(job_id, processed_delta=1, skipped_delta=1)
                return URLProcessingResult(
                    url=raw_url,
                    status="SKIPPED",
                    error=ProcessingError(
                        category="ROBOTS_DISALLOWED",
                        message="Excluded by robots.txt policy",
                        attempt=1,
                        recoverable=False,
                    ),
                )

        # Step 4: Mark URL PROCESSING in storage
        if self.storage:
            await self.storage.update_url_status(job_id, normalized, "PROCESSING")

        try:
            # Step 5-8: HTTPX Retrieval
            retrieval = await self.retriever.retrieve(raw_url, config)

            # Step 9-10: Evaluate content sufficiency & trigger Playwright fallback if necessary
            if config.javascript_fallback and self.renderer:
                if needs_javascript_rendering(retrieval):
                    logger.info(f"Invoking Playwright fallback for dynamic URL: {raw_url}")
                    rendered = await self.renderer.render(raw_url, config)
                    if rendered.success and rendered.content:
                        retrieval = rendered

            # Handle retrieval failure
            if not retrieval.success or not retrieval.content:
                err = retrieval.error or ProcessingError(
                    category="NETWORK_ERROR",
                    message="Failed to retrieve content from target URL",
                    attempt=1,
                    recoverable=False,
                )
                if self.error_manager:
                    await self.error_manager.record(job_id, err)
                if self.storage:
                    await self.storage.update_url_status(job_id, normalized, "FAILED")
                    await self.storage.update_job_counters(job_id, processed_delta=1, failed_delta=1)

                return URLProcessingResult(
                    url=raw_url,
                    status="FAILED",
                    error=err,
                )

            # Step 11-12: Parse
            parsed = self.parser.parse(retrieval)

            # Step 13: Extract
            extracted = self.extractor.extract(parsed)

            # Step 14-15: Preprocess & Hash (assembles ProcessedDocument)
            processed_doc = self.preprocessor.preprocess(
                extracted=extracted,
                job_id=job_id,
                url=raw_url,
                crawl_depth=crawl_item.depth,
            )

            # Step 21-23: Media processing (images & documents) concurrently
            all_media = list(processed_doc.images) + list(processed_doc.documents)
            if all_media:
                downloaded = await asyncio.gather(*(self.media_downloader.download(m, job_id) for m in all_media))
                processed_doc.images = [m for m in downloaded if m.media_type != "pdf"]
                processed_doc.documents = [m for m in downloaded if m.media_type == "pdf"]

            # Step 16: Persist page to storage
            if self.storage:
                await self.storage.save_page(processed_doc)
                await self.storage.update_url_status(job_id, normalized, "SUCCESS")
                await self.storage.update_job_counters(job_id, processed_delta=1, successful_delta=1)

            # Step 17-18: Discovered links extraction
            discovered = [link.url for link in processed_doc.links]

            return URLProcessingResult(
                url=raw_url,
                status="SUCCESS",
                page=processed_doc,
                discovered_links=discovered,
                media=list(processed_doc.images) + list(processed_doc.documents),
            )

        except Exception as exc:
            err = self.error_manager.classify_exception(exc)
            logger.warning(f"URL processing failure on {raw_url}: {err.message}")

            if self.error_manager:
                await self.error_manager.record(job_id, err)
            if self.storage:
                await self.storage.update_url_status(job_id, normalized, "FAILED")
                await self.storage.update_job_counters(job_id, processed_delta=1, failed_delta=1)

            return URLProcessingResult(
                url=raw_url,
                status="FAILED",
                error=err,
            )

    async def crawl(
        self,
        job_id: str,
        seed_urls: List[str],
        config: CrawlConfig,
        url_manager: Optional[URLManager] = None,
    ) -> List[ProcessedDocument]:
        """
        Executes complete BFS crawl loop until the queue is exhausted.
        Enforces depth bounds, deduplication, and per-URL checkpointing.
        """
        mgr = url_manager or URLManager(max_depth=config.crawl_depth, recursive=config.recursive)

        # Enqueue seed URLs
        for seed in seed_urls:
            item = mgr.add_url(seed, depth=0)
            if item and self.storage:
                rec = await self.storage.add_url(
                    job_id=job_id,
                    url=item.url,
                    normalized_url=item.normalized_url,
                    depth=item.depth,
                )
                if rec:
                    await self.storage.update_job_counters(job_id, total_delta=1)

        processed_documents: List[ProcessedDocument] = []
        concurrency = max(1, config.max_concurrency)
        sem = asyncio.Semaphore(concurrency)
        crawled_count = 0

        async def _worker_process(item: CrawlURL):
            async with sem:
                logger.info(
                    f"[{job_id}] Crawling depth {item.depth}/{config.crawl_depth}: {item.url}"
                )
                return item, await self.process_url(item, config, job_id)

        # BFS Crawl Loop with bounded concurrency & max_urls enforcement
        while mgr.has_next():
            if config.max_urls is not None and crawled_count >= config.max_urls:
                logger.info(
                    f"[{job_id}] Reached max_urls limit ({config.max_urls}). Halting crawl."
                )
                break

            batch = []
            batch_limit = concurrency
            if config.max_urls is not None:
                remaining = config.max_urls - crawled_count
                if remaining <= 0:
                    break
                batch_limit = min(concurrency, remaining)

            while mgr.has_next() and len(batch) < batch_limit:
                item = mgr.get_next()
                if item:
                    batch.append(item)

            if not batch:
                break

            results = await asyncio.gather(*(_worker_process(item) for item in batch))
            crawled_count += len(batch)

            for current_item, result in results:
                if result.status == "SUCCESS" and result.page:
                    processed_documents.append(result.page)

                    # Expand discovered links if recursive, depth allows, and URL limit not reached
                    if (
                        config.recursive
                        and current_item.depth < config.crawl_depth
                        and (config.max_urls is None or crawled_count < config.max_urls)
                    ):
                        newly_discovered_count = 0
                        for child_url in result.discovered_links:
                            new_item = mgr.add_url(
                                child_url,
                                depth=current_item.depth + 1,
                                base_url=current_item.url,
                                parent_url_id=current_item.normalized_url,
                            )
                            if new_item:
                                newly_discovered_count += 1
                                if self.storage:
                                    await self.storage.add_url(
                                        job_id=job_id,
                                        url=new_item.url,
                                        normalized_url=new_item.normalized_url,
                                        depth=new_item.depth,
                                        parent_url_id=current_item.normalized_url,
                                    )

                        if newly_discovered_count > 0 and self.storage:
                            await self.storage.update_job_counters(job_id, total_delta=newly_discovered_count)

        if config.max_urls is not None and crawled_count >= config.max_urls:
            logger.info(f"[{job_id}] Crawl halted at URL limit: {crawled_count}/{config.max_urls} URLs crawled.")
            if self.storage and hasattr(self.storage, "cleanup_pending_job_urls"):
                try:
                    await self.storage.cleanup_pending_job_urls(job_id)
                except Exception:
                    pass

        logger.info(f"[{job_id}] Crawl complete. Processed {len(processed_documents)} pages (Total URLs crawled: {crawled_count}).")
        return processed_documents
