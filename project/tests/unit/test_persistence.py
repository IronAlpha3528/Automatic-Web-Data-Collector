"""
Unit tests for Phase 8: Persistence Layer (Storage, MediaDownloader, ErrorManager).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from project.schemas.page_schema import MediaReference, ProcessedDocument, PageMetadata, DocumentLink
from project.schemas.result_schema import ProcessingError
from project.interfaces.storage import Storage
from project.interfaces.media import MediaDownloader
from project.services.storage import PostgresStorage
from project.services.media_downloader import DefaultMediaDownloader
from project.services.error_manager import ErrorManager
from project.utils.exceptions import TimeoutError, HTTPError, NetworkError, ParsingError, PersistenceError


class TestErrorManager:
    """Validates error taxonomy classification and job-level fault isolation rules."""

    def test_error_classification(self):
        em = ErrorManager()

        p_err = em.classify_exception(TimeoutError("Operation timed out"), attempt=2)
        assert p_err.category == "TIMEOUT_ERROR"
        assert p_err.attempt == 2
        assert p_err.recoverable is True

        h_err = em.classify_exception(HTTPError("Service Unavailable", status_code=503), attempt=1)
        assert h_err.category == "HTTP_ERROR"
        assert h_err.recoverable is True

        h_err404 = em.classify_exception(HTTPError("Not Found", status_code=404), attempt=1)
        assert h_err404.category == "HTTP_ERROR"
        assert h_err404.recoverable is False

        net_err = em.classify_exception(NetworkError("DNS resolution failed"), attempt=1)
        assert net_err.category == "NETWORK_ERROR"

        parse_err = em.classify_exception(ParsingError("Malformed HTML"), attempt=1)
        assert parse_err.category == "PARSING_ERROR"

        db_err = em.classify_exception(PersistenceError("DB connection lost"), attempt=1)
        assert db_err.category == "DATABASE_ERROR"

    def test_golden_failure_rule_fault_isolation(self):
        """Golden Rule: Webpage errors do not abort job; only database/system errors do."""
        em = ErrorManager()

        url_err = ProcessingError(category="TIMEOUT_ERROR", message="Timeout", attempt=3)
        assert em.is_job_terminating_failure(url_err) is False

        http_err = ProcessingError(category="HTTP_ERROR", message="404", attempt=1)
        assert em.is_job_terminating_failure(http_err) is False

        db_err = ProcessingError(category="DATABASE_ERROR", message="Fatal", attempt=1)
        assert em.is_job_terminating_failure(db_err) is True


class TestMediaDownloader:
    """Validates media file extension resolution and protocol conformance."""

    def test_protocol_conformance(self):
        downloader = DefaultMediaDownloader()
        assert isinstance(downloader, MediaDownloader)

    def test_extension_resolution(self):
        downloader = DefaultMediaDownloader()

        assert downloader._resolve_extension("https://example.com/logo.png", None, "image") == ".png"
        assert downloader._resolve_extension("https://example.com/doc.pdf", None, "pdf") == ".pdf"
        assert downloader._resolve_extension("https://example.com/asset?id=123", "image/jpeg", "image") in (".jpeg", ".jpg")
        assert downloader._resolve_extension("https://example.com/download", "application/pdf", "pdf") == ".pdf"

    @pytest.mark.anyio
    async def test_download_failure_isolation(self):
        """Ensures network or invalid host failures do not raise exceptions, but mark status='failed'."""
        downloader = DefaultMediaDownloader(timeout=1)
        ref = MediaReference(url="https://invalid-non-existent-domain-12345.org/test.jpg", media_type="image")
        result = await downloader.download(ref, job_id="test-job-001")
        assert result.status == "failed"


class TestPostgresStorageProtocol:
    """Validates Storage protocol conformance."""

    def test_protocol_conformance(self):
        storage = PostgresStorage()
        assert isinstance(storage, Storage)
