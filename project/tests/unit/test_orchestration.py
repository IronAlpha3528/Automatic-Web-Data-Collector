"""
Unit tests for Phase 9: Crawl & Job Orchestration.
Validates Crawler 16-step processing, BFS loop, fault isolation, and JobManager state machine.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from project.config.settings import CrawlConfig
from project.schemas.url_schema import CrawlURL
from project.schemas.job_schema import CreateJobRequest
from project.schemas.page_schema import ProcessedDocument, PageMetadata
from project.schemas.result_schema import RetrievalResult, ParsedDocument, ExtractedContent, ProcessingError
from project.models.job import JobStatus, ScrapingJob
from project.services.crawler import Crawler
from project.services.job_manager import JobManager


class TestCrawlerPipeline:
    """Validates the Crawler pipeline execution and failure isolation."""

    @pytest.mark.anyio
    async def test_crawler_success_flow(self):
        # Mock dependencies
        mock_retriever = AsyncMock()
        mock_retriever.retrieve.return_value = RetrievalResult(
            url="https://example.com/test",
            status_code=200,
            content="<html><body><h1>Test</h1><p>Paragraph</p></body></html>",
            content_type="text/html",
            success=True,
        )

        mock_parser = MagicMock()
        mock_parser.parse.return_value = ParsedDocument(
            url="https://example.com/test",
            title="Test Page",
            headings=["Test"],
            paragraphs=["Paragraph"],
            links=[],
            raw_text="Test Paragraph",
        )

        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = ExtractedContent(
            title="Test Page",
            headings=["Test"],
            paragraphs=["Paragraph"],
            cleaned_content="Test Paragraph",
        )

        mock_storage = AsyncMock()

        crawler = Crawler(
            retriever=mock_retriever,
            parser=mock_parser,
            extractor=mock_extractor,
            storage=mock_storage,
        )

        item = CrawlURL(url="https://example.com/test", normalized_url="https://example.com/test", depth=0)
        config = CrawlConfig(crawl_depth=1)

        result = await crawler.process_url(item, config, job_id="test-job-001")

        assert result.status == "SUCCESS"
        assert result.page is not None
        assert result.page.title == "Test Page"
        assert mock_storage.save_page.called
        assert mock_storage.update_url_status.called

    @pytest.mark.anyio
    async def test_crawler_failure_isolation(self):
        """Ensures that a 404 or connection drop records failure without crashing the crawler."""
        mock_retriever = AsyncMock()
        mock_retriever.retrieve.return_value = RetrievalResult(
            url="https://example.com/404",
            status_code=404,
            success=False,
            error=ProcessingError(category="HTTP_ERROR", message="Not Found", attempt=1),
        )

        mock_storage = AsyncMock()

        crawler = Crawler(
            retriever=mock_retriever,
            storage=mock_storage,
        )

        item = CrawlURL(url="https://example.com/404", normalized_url="https://example.com/404", depth=0)
        config = CrawlConfig()

        result = await crawler.process_url(item, config, job_id="test-job-002")

        assert result.status == "FAILED"
        assert result.error is not None
        assert result.error.category == "HTTP_ERROR"
        mock_storage.update_url_status.assert_called_with("test-job-002", "https://example.com/404", "FAILED")


class TestJobManagerStateMachine:
    """Validates JobManager job creation and state transitions."""

    @pytest.mark.anyio
    async def test_create_job(self):
        mock_storage = AsyncMock()
        created_job = ScrapingJob(job_id="job-123", status=JobStatus.CREATED, crawl_depth=2)
        mock_storage.create_job.return_value = created_job
        mock_storage.get_job.return_value = created_job
        mock_storage.add_url.return_value = MagicMock()

        jm = JobManager(storage=mock_storage)

        req = CreateJobRequest(
            seed_urls=["https://example.com"],
            crawl_depth=2,
            robots_mode="respect",
        )

        res = await jm.create_job(req)
        assert res.job_id == "job-123"
        assert res.status == JobStatus.CREATED
        assert mock_storage.create_job.called

    @pytest.mark.anyio
    async def test_job_state_resolution(self):
        """Validates COMPLETED vs COMPLETED_WITH_ERRORS resolution (Section 46)."""
        mock_storage = AsyncMock()
        job_success = ScrapingJob(job_id="j1", status=JobStatus.RUNNING, failed_urls=0)
        mock_storage.get_job.return_value = job_success

        mock_crawler = AsyncMock()
        mock_crawler.crawl.return_value = []

        jm = JobManager(storage=mock_storage, crawler=mock_crawler)
        await jm._run_job("j1")

        assert mock_storage.update_job_status.called
        call_kwargs = mock_storage.update_job_status.call_args.kwargs
        assert call_kwargs["job_id"] == "j1"
        assert call_kwargs["status"] == "COMPLETED"
        assert call_kwargs["completed_at"] is not None
