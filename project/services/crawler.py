"""
Crawler service executing Breadth-First Search (BFS) link traversal and content pipeline.
Adheres to Section 44 (Crawler Contract) and Section 45 (URL Processing Algorithm).
"""
import asyncio
from typing import Optional, List, Dict, Set
from project.config.settings import CrawlConfig
from project.schemas.url_schema import CrawlURL
from project.schemas.page_schema import ProcessedDocument, PageMetadata, MediaReference
from project.schemas.result_schema import URLProcessingResult, ProcessingError
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
from project.utils.url_normalizer import normalize_url, is_valid_url
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

            # Step 21-23: Media processing (images & documents)
            downloaded_images = []
            for img in processed_doc.images:
                dl_img = await self.media_downloader.download(img, job_id)
                downloaded_images.append(dl_img)
            processed_doc.images = downloaded_images

            downloaded_docs = []
            for doc_ref in processed_doc.documents:
                dl_doc = await self.media_downloader.download(doc_ref, job_id)
                downloaded_docs.append(dl_doc)
            processed_doc.documents = downloaded_docs

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
                await self.storage.add_url(
                    job_id=job_id,
                    url=item.url,
                    normalized_url=item.normalized_url,
                    depth=item.depth,
                )

        if self.storage:
            await self.storage.update_job_counters(job_id, total_delta=mgr.total_discovered)

        processed_documents: List[ProcessedDocument] = []

        # BFS Crawl Loop
        while mgr.has_next():
            current_item = mgr.get_next()
            if not current_item:
                break

            logger.info(
                f"[{job_id}] Crawling depth {current_item.depth}/{config.crawl_depth}: {current_item.url}"
            )

            result = await self.process_url(current_item, config, job_id)

            if result.status == "SUCCESS" and result.page:
                processed_documents.append(result.page)

                # Expand discovered links if recursive and depth allows
                if config.recursive and current_item.depth < config.crawl_depth:
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

        logger.info(f"[{job_id}] Crawl complete. Processed {len(processed_documents)} pages.")
        return processed_documents
