"""
Phase 13: End-to-End System Acceptance Test.
Validates Section 67 (Definition of Done) and complete lifecycle:
Job Creation -> Job Execution -> BFS Traversal -> Content Preprocessing -> Persistence -> JSON Export -> API Verification.
"""
import os
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from project.config.settings import CrawlConfig
from project.models.job import JobStatus, ScrapingJob
from project.models.url_record import URLStatus, URLRecord
from project.schemas.job_schema import CreateJobRequest
from project.schemas.result_schema import RetrievalResult
from project.services.crawler import Crawler
from project.services.job_manager import JobManager
from project.services.json_exporter import JSONExporter
from project.app import app


class TestSystemEndToEndAcceptance:
    """Verifies complete end-to-end crawler, storage, exporter, and API lifecycle."""

    @pytest.mark.anyio
    async def test_complete_job_lifecycle_e2e(self, tmp_path):
        # 1. Setup mock storage state
        jobs_db = {}
        urls_db = {}
        pages_db = {}

        mock_storage = AsyncMock()

        async def mock_create_job(job_id, config):
            job = ScrapingJob(
                job_id=job_id,
                status=JobStatus.CREATED,
                crawl_depth=config.crawl_depth,
                recursive=config.recursive,
                javascript_fallback=config.javascript_fallback,
                robots_mode=config.robots_mode,
                timeout_seconds=config.timeout_seconds,
                max_retries=config.max_retries,
                domain_rate_limit=config.domain_rate_limit,
                max_concurrency=config.max_concurrency,
                total_urls=0,
                processed_urls=0,
                successful_urls=0,
                failed_urls=0,
                skipped_urls=0,
            )
            jobs_db[job_id] = job
            return job

        async def mock_get_job(job_id):
            return jobs_db.get(job_id)

        async def mock_update_status(job_id, status, error=None, started_at=None, completed_at=None):
            if job_id in jobs_db:
                jobs_db[job_id].status = status
                if error:
                    jobs_db[job_id].error_message = error

        async def mock_add_url(job_id, url, normalized_url, depth, parent_url_id=None):
            rec = URLRecord(
                url_id=f"url-{len(urls_db)+1}",
                job_id=job_id,
                url=url,
                normalized_url=normalized_url,
                depth=depth,
                status=URLStatus.QUEUED,
            )
            urls_db[normalized_url] = rec
            return rec

        async def mock_update_url_status(job_id, url, status, error=None):
            for rec in urls_db.values():
                if rec.url == url or rec.normalized_url == url:
                    rec.status = status

        async def mock_save_page(page_doc):
            pages_db[page_doc.url] = page_doc

        async def mock_update_job_counters(
            job_id,
            total_delta=0,
            processed_delta=0,
            successful_delta=0,
            failed_delta=0,
            skipped_delta=0,
            **kwargs,
        ):
            job = jobs_db.get(job_id)
            if job:
                job.total_urls += total_delta
                job.processed_urls += processed_delta
                job.successful_urls += successful_delta
                job.failed_urls += failed_delta
                job.skipped_urls += skipped_delta

        async def mock_get_url_records(job_id):
            return [rec for rec in urls_db.values() if rec.job_id == job_id]

        async def mock_list_jobs(limit=50, offset=0):
            return list(jobs_db.values())

        mock_storage.create_job.side_effect = mock_create_job
        mock_storage.get_job.side_effect = mock_get_job
        mock_storage.list_jobs.side_effect = mock_list_jobs
        mock_storage.update_job_status.side_effect = mock_update_status
        mock_storage.add_url.side_effect = mock_add_url
        mock_storage.update_url_status.side_effect = mock_update_url_status
        mock_storage.save_page.side_effect = mock_save_page
        mock_storage.update_job_counters.side_effect = mock_update_job_counters
        mock_storage.get_url_records_by_job.side_effect = mock_get_url_records

        # 2. Mock Retriever with 2 pages for BFS traversal
        mock_retriever = AsyncMock()
        page_html_1 = """
        <html>
            <head><title>Seed Page</title></head>
            <body>
                <h1>Welcome to Acceptance Testing</h1>
                <p>This is the initial seed page with essential content.</p>
                <a href="https://example.com/child-page">Child Page Link</a>
                <img src="https://example.com/img/banner.png" alt="Banner">
            </body>
        </html>
        """
        page_html_2 = """
        <html>
            <head><title>Child Page</title></head>
            <body>
                <h1>Child Document Details</h1>
                <p>Deeper level content crawled recursively by BFS traversal.</p>
            </body>
        </html>
        """

        async def mock_retrieve(url, cfg):
            if "child" in url:
                return RetrievalResult(
                    url=url,
                    status_code=200,
                    content=page_html_2,
                    content_type="text/html",
                    success=True,
                )
            return RetrievalResult(
                url=url,
                status_code=200,
                content=page_html_1,
                content_type="text/html",
                success=True,
            )

        mock_retriever.retrieve.side_effect = mock_retrieve

        # Mock media downloader to avoid real network attempts
        mock_media_downloader = AsyncMock()
        mock_media_downloader.download.side_effect = lambda ref, job_id: ref

        # 3. Assemble Crawler and JobManager
        exporter = JSONExporter(base_output_dir=str(tmp_path))
        crawler = Crawler(
            retriever=mock_retriever,
            storage=mock_storage,
            media_downloader=mock_media_downloader,
        )
        job_manager = JobManager(
            storage=mock_storage,
            crawler=crawler,
            exporter=exporter,
        )

        # 4. Initiate Job
        job_request = CreateJobRequest(
            seed_urls=["https://example.com/start"],
            crawl_depth=1,
            recursive=True,
        )
        created_job = await job_manager.create_job(job_request)
        assert created_job.job_id is not None
        assert created_job.status == JobStatus.CREATED

        # 5. Execute Job Execution Flow
        start_resp = await job_manager.start_job(created_job.job_id)
        assert start_resp.status == JobStatus.RUNNING

        # Wait for the background worker task to complete
        task = job_manager._active_tasks.get(created_job.job_id)
        if task:
            await task

        completed_job = await mock_storage.get_job(created_job.job_id)
        assert completed_job.status == JobStatus.COMPLETED
        assert completed_job.processed_urls >= 2

        # 6. Verify Export File Generated & Conforms to Appendix B schema
        export_file = os.path.join(
            str(tmp_path), "jobs", created_job.job_id, "json", f"{created_job.job_id}_results.json"
        )
        assert os.path.isfile(export_file), f"Expected export file at {export_file}"

        with open(export_file, "r", encoding="utf-8") as f:
            export_payload = json.load(f)

        assert isinstance(export_payload, list)
        assert len(export_payload) >= 2
        first_doc = export_payload[0]
        assert "url" in first_doc
        assert "title" in first_doc
        assert "metadata" in first_doc
        assert "content_hash" in first_doc["metadata"]

        # 7. Verify Web App Client Endpoints (API & UI)
        from project.routes.jobs import get_job_manager
        from httpx import AsyncClient, ASGITransport

        app.dependency_overrides[get_job_manager] = lambda: job_manager
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                dashboard_resp = await client.get("/")
                assert dashboard_resp.status_code == 200
                assert "Scraping Jobs Dashboard" in dashboard_resp.text

                # Check job details endpoint
                api_resp = await client.get(f"/api/jobs/{created_job.job_id}")
                assert api_resp.status_code == 200
                assert api_resp.json()["job_id"] == created_job.job_id
        finally:
            app.dependency_overrides.clear()
