"""
Unit and integration tests for Phase 11 (API) and Phase 12 (Web UI).
Uses FastAPI dependency overrides to isolate from live database infrastructure.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock

from project.app import app
from project.routes.jobs import get_job_manager
from project.models.job import JobStatus, ScrapingJob
from project.schemas.job_schema import JobResponse


@pytest.fixture
def mock_job():
    return ScrapingJob(
        job_id="test-api-job-001",
        status=JobStatus.CREATED,
        crawl_depth=2,
        total_urls=1,
    )


@pytest.fixture
def mock_manager(mock_job):
    mgr = AsyncMock()
    mgr.list_jobs.return_value = [JobResponse.model_validate(mock_job)]
    mgr.get_job.return_value = JobResponse.model_validate(mock_job)
    mgr.create_job.return_value = JobResponse.model_validate(mock_job)
    mgr.start_job.return_value = JobResponse.model_validate(
        ScrapingJob(job_id="test-api-job-001", status=JobStatus.RUNNING)
    )
    mgr.cancel_job.return_value = JobResponse.model_validate(
        ScrapingJob(job_id="test-api-job-001", status=JobStatus.FAILED)
    )
    return mgr


class TestWebUI:
    """Validates HTML presentation routes and template rendering."""

    @pytest.mark.anyio
    async def test_dashboard_page(self, mock_manager):
        app.dependency_overrides[get_job_manager] = lambda: mock_manager
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/")
                assert response.status_code == 200
                assert "Scraping Jobs Dashboard" in response.text
                assert "New Scraping Job" in response.text
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_create_job_page(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/jobs/new")
            assert response.status_code == 200
            assert "New Scraping Job Configuration" in response.text
            assert 'name="seed_urls"' in response.text


class TestJobsRESTAPI:
    """Validates FastAPI REST endpoints conforming to Section 34."""

    @pytest.mark.anyio
    async def test_create_job_endpoint(self, mock_manager):
        app.dependency_overrides[get_job_manager] = lambda: mock_manager
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                payload = {
                    "seed_urls": ["https://example.com/test"],
                    "crawl_depth": 2,
                    "recursive": True,
                    "javascript_fallback": True,
                    "robots_mode": "respect",
                    "timeout_seconds": 15,
                    "max_retries": 3,
                    "domain_rate_limit": 2.0,
                    "max_concurrency": 3,
                }
                res = await client.post("/api/jobs", json=payload)
                assert res.status_code == 201
                data = res.json()
                assert data["job_id"] == "test-api-job-001"
                assert data["status"] == "CREATED"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_get_job_details(self, mock_manager):
        app.dependency_overrides[get_job_manager] = lambda: mock_manager
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                res = await client.get("/api/jobs/test-api-job-001")
                assert res.status_code == 200
                assert res.json()["job_id"] == "test-api-job-001"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_get_job_not_found(self, mock_manager):
        mock_manager.get_job.return_value = None
        app.dependency_overrides[get_job_manager] = lambda: mock_manager
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                res = await client.get("/api/jobs/non-existent-id")
                assert res.status_code == 404
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_start_job_endpoint(self, mock_manager):
        app.dependency_overrides[get_job_manager] = lambda: mock_manager
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                res = await client.post("/api/jobs/test-api-job-001/start")
                assert res.status_code == 200
                assert res.json()["status"] == "RUNNING"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_cancel_job_endpoint(self, mock_manager):
        app.dependency_overrides[get_job_manager] = lambda: mock_manager
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                res = await client.post("/api/jobs/test-api-job-001/cancel")
                assert res.status_code == 200
                assert res.json()["status"] == "FAILED"
        finally:
            app.dependency_overrides.clear()
