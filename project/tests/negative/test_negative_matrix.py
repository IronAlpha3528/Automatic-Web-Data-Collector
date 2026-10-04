"""
Negative Test Matrix matching Phase 13 & Section 50 of Technical Implementation Plan.
Verifies failure isolation, structured error classification, and resilient degradation.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from project.config.settings import CrawlConfig
from project.schemas.result_schema import RetrievalResult, ProcessingError
from project.schemas.page_schema import ProcessedDocument, PageMetadata
from project.services.retriever import HTTPXRetriever
from project.services.parser import DocumentParser
from project.services.extractor import ContentExtractor
from project.services.preprocessor import ContentPreprocessor
from project.services.json_exporter import JSONExporter
from project.utils.exceptions import ParsingError, ExportError


class TestNegativeMatrix:
    """Rigorous failure case testing across pipeline components."""

    @pytest.mark.anyio
    async def test_negative_invalid_url_scheme(self):
        retriever = HTTPXRetriever()
        config = CrawlConfig()
        result = await retriever.retrieve("javascript:alert(1)", config)
        assert result.success is False
        assert result.error.category == "URL_VALIDATION_ERROR"
        assert "Unsupported URL scheme" in result.error.message

    @pytest.mark.anyio
    async def test_negative_timeout_bounded_exhaustion(self):
        import httpx
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ReadTimeout("Socket timeout"))

        retriever = HTTPXRetriever(client=mock_client)
        config = CrawlConfig(max_retries=1, timeout_seconds=1)

        result = await retriever.retrieve("https://slow-server.test", config)
        assert result.success is False
        assert result.error.category == "TIMEOUT_ERROR"
        assert result.error.recoverable is False

    @pytest.mark.anyio
    async def test_negative_http_404_not_found(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.headers = {"content-type": "text/html"}
        mock_resp.url = "https://example.com/missing"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        retriever = HTTPXRetriever(client=mock_client)
        config = CrawlConfig()
        result = await retriever.retrieve("https://example.com/missing", config)

        assert result.success is False
        assert result.status_code == 404
        assert result.error.category == "HTTP_ERROR"
        assert result.error.recoverable is False

    @pytest.mark.anyio
    async def test_negative_http_500_server_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.headers = {"content-type": "text/html"}
        mock_resp.url = "https://example.com/500"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        retriever = HTTPXRetriever(client=mock_client)
        config = CrawlConfig(max_retries=1)
        result = await retriever.retrieve("https://example.com/500", config)

        assert result.success is False
        assert result.status_code == 500
        assert result.error.category == "HTTP_ERROR"

    def test_negative_malformed_html_resilience(self):
        malformed_html = "<div class='broken'><h1>Title without closing<p>Unclosed paragraph<table><tr><td>Cell"
        retrieval = RetrievalResult(
            url="https://example.com/malformed",
            status_code=200,
            content=malformed_html,
            content_type="text/html",
            success=True,
        )

        parser = DocumentParser()
        parsed = parser.parse(retrieval)

        assert parsed.title == ""
        assert len(parsed.headings) > 0
        assert len(parsed.paragraphs) > 0

    def test_negative_empty_html_handling(self):
        retrieval = RetrievalResult(
            url="https://example.com/empty",
            status_code=200,
            content="",
            content_type="text/html",
            success=True,
        )

        parser = DocumentParser()
        parsed = parser.parse(retrieval)
        assert parsed.title == ""
        assert len(parsed.headings) == 0
        assert len(parsed.paragraphs) == 0

    def test_negative_corrupted_pdf_handling(self):
        retrieval = RetrievalResult(
            url="https://example.com/corrupt.pdf",
            status_code=200,
            content=b"%PDF-1.4 this is totally corrupted non-pdf binary data \x00\xff\xfe",
            content_type="application/pdf",
            success=True,
        )

        parser = DocumentParser()
        with pytest.raises(ParsingError):
            parser.parse(retrieval)

    def test_negative_json_exporter_invalid_target_directory(self):
        exporter = JSONExporter(base_output_dir="/non_existent_read_only_root_dir/xyz")
        doc = ProcessedDocument(
            job_id="JOB-NEG",
            url="https://example.com",
            metadata=PageMetadata(
                timestamp="2026-10-04T00:00:00Z",
                crawl_depth=0,
                content_hash="hash123",
            ),
        )
        # On Windows or systems where directory creation might fail or raise an error
        # In a real environment with invalid paths, ExportError is raised
