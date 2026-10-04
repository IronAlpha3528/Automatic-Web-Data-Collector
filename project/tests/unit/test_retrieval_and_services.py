"""
Unit tests for Phase 3 (Retrieval), Phase 4 (Rendering), Phase 5 (Parsing),
Phase 6 (Extraction), Phase 7 (Preprocessing), and Phase 10 (Export).
"""
import os
import json
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from project.config.settings import CrawlConfig, settings
from project.schemas.result_schema import RetrievalResult, ParsedDocument, ExtractedContent, ProcessingError
from project.schemas.page_schema import ProcessedDocument, DocumentLink, MediaReference
from project.interfaces import Retriever, Renderer, Parser, Extractor
from project.services.retriever import HTTPXRetriever
from project.services.renderer import PlaywrightRenderer
from project.services.parser import DocumentParser
from project.services.extractor import ContentExtractor
from project.services.preprocessor import ContentPreprocessor
from project.services.json_exporter import JSONExporter
from project.utils.retry import execute_with_retry, is_retryable_status_code
from project.utils.rate_limiter import DomainRateLimiter
from project.utils.content_detection import needs_javascript_rendering
from project.utils.hashing import compute_content_hash
from project.utils.exceptions import TimeoutError, NetworkError, HTTPError, ExportError


class TestPhase3Retrieval:
    """Unit tests for Phase 3 (HTTPX retrieval, retry logic, rate limiter)."""

    def test_status_code_retryability(self):
        assert is_retryable_status_code(500) is True
        assert is_retryable_status_code(502) is True
        assert is_retryable_status_code(503) is True
        assert is_retryable_status_code(504) is True
        assert is_retryable_status_code(429) is True
        assert is_retryable_status_code(404) is False
        assert is_retryable_status_code(403) is False
        assert is_retryable_status_code(200) is False

    @pytest.mark.anyio
    async def test_retry_success_on_first_try(self):
        calls = 0

        async def op(attempt: int):
            nonlocal calls
            calls += 1
            return "success"

        res = await execute_with_retry(op, max_retries=3, base_delay=0.01)
        assert res == "success"
        assert calls == 1

    @pytest.mark.anyio
    async def test_retry_success_after_transient_failure(self):
        calls = 0

        async def op(attempt: int):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise TimeoutError("Simulated timeout")
            return "recovered"

        res = await execute_with_retry(op, max_retries=3, base_delay=0.01)
        assert res == "recovered"
        assert calls == 2

    @pytest.mark.anyio
    async def test_retry_non_retryable_fails_immediately(self):
        calls = 0

        async def op(attempt: int):
            nonlocal calls
            calls += 1
            raise ValueError("Fatal validation problem")

        with pytest.raises(ValueError):
            await execute_with_retry(op, max_retries=3, base_delay=0.01)
        assert calls == 1

    @pytest.mark.anyio
    async def test_domain_rate_limiter(self):
        limiter = DomainRateLimiter(default_rate_limit=10.0)
        await limiter.acquire("https://example.com/page1")
        await limiter.acquire("https://example.com/page2")
        limiter.reset()

    @pytest.mark.anyio
    async def test_httpx_retriever_unsupported_scheme(self):
        retriever = HTTPXRetriever()
        config = CrawlConfig()
        res = await retriever.retrieve("ftp://example.com/file.txt", config)
        assert res.success is False
        assert res.error.category == "URL_VALIDATION_ERROR"

    @pytest.mark.anyio
    async def test_httpx_retriever_mock_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_response.text = "<html><head><title>Test</title></head><body><h1>Hello World</h1></body></html>"
        mock_response.url = "https://example.com/test"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        retriever = HTTPXRetriever(client=mock_client)
        config = CrawlConfig()
        res = await retriever.retrieve("https://example.com/test", config)

        assert res.success is True
        assert res.status_code == 200
        assert "Hello World" in res.content
        assert res.error is None

    @pytest.mark.anyio
    async def test_httpx_retriever_404_isolated(self):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = {"content-type": "text/html"}
        mock_response.url = "https://example.com/404"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        retriever = HTTPXRetriever(client=mock_client)
        config = CrawlConfig(max_retries=0)
        res = await retriever.retrieve("https://example.com/404", config)

        assert res.success is False
        assert res.status_code == 404
        assert res.error.category == "HTTP_ERROR"


class TestPhase4Rendering:
    """Unit tests for Phase 4 (Content sufficiency detection and Playwright renderer)."""

    def test_content_detection_sufficient_html(self):
        html = """
        <html>
            <head><title>Full Page</title></head>
            <body>
                <h1>Welcome to our site</h1>
                <p>This is a complete article with plenty of text and meaningful paragraphs detailing our services.</p>
            </body>
        </html>
        """
        assert needs_javascript_rendering(html, "text/html") is False

    def test_content_detection_empty_spa(self):
        spa_html = """
        <html>
            <head><title>React App</title></head>
            <body>
                <div id="root"></div>
                <script src="/bundle.js"></script>
            </body>
        </html>
        """
        assert needs_javascript_rendering(spa_html, "text/html") is True

    def test_content_detection_pdf_bypass(self):
        assert needs_javascript_rendering(b"%PDF-1.4...", "application/pdf") is False

    @pytest.mark.anyio
    async def test_playwright_renderer_interface(self):
        renderer = PlaywrightRenderer()
        assert isinstance(renderer, Renderer)
        # Invalid scheme check
        config = CrawlConfig()
        res = await renderer.render("file:///tmp/test.html", config)
        assert res.success is False
        assert res.error.category == "URL_VALIDATION_ERROR"
        await renderer.close()


class TestPhase5Parsing:
    """Unit tests for Phase 5 (DocumentParser with HTML and PDF)."""

    def test_parse_html_complete_structure(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Sample Article</title></head>
        <body>
            <h1>Main Title</h1>
            <h2>Subtitle</h2>
            <p>First paragraph about software engineering.</p>
            <p>Second paragraph with details.</p>
            <table>
                <tr><th>Name</th><th>Role</th></tr>
                <tr><td>Alice</td><td>Developer</td></tr>
            </table>
            <a href="/about">About Us</a>
            <a href="https://example.com/doc.pdf">Download Guide</a>
            <img src="/img/logo.png" alt="Logo">
        </body>
        </html>
        """
        retrieval = RetrievalResult(
            url="https://example.com/article",
            status_code=200,
            content=html,
            content_type="text/html",
            success=True,
        )

        parser = DocumentParser()
        parsed = parser.parse(retrieval)

        assert parsed.title == "Sample Article"
        assert parsed.headings == ["Main Title", "Subtitle"]
        assert len(parsed.paragraphs) == 2
        assert len(parsed.raw_tables) == 1
        assert parsed.raw_tables[0] == [["Name", "Role"], ["Alice", "Developer"]]
        assert any(link.url == "https://example.com/about" for link in parsed.links)
        assert "https://example.com/doc.pdf" in parsed.pdf_urls
        assert "https://example.com/img/logo.png" in parsed.image_urls

    def test_parse_failed_retrieval(self):
        retrieval = RetrievalResult(
            url="https://example.com/failed",
            success=False,
            error=ProcessingError(category="HTTP_ERROR", message="404"),
        )
        parser = DocumentParser()
        parsed = parser.parse(retrieval)
        assert parsed.title == ""
        assert len(parsed.headings) == 0


class TestPhase6Extraction:
    """Unit tests for Phase 6 (ContentExtractor)."""

    def test_extractor_isolates_meaningful_content(self):
        parsed = ParsedDocument(
            url="https://example.com/post",
            title="Clean Title",
            headings=["Section 1"],
            paragraphs=[
                "Privacy Policy notice",
                "This is the core content of the blog post.",
                "Here is another relevant paragraph.",
            ],
            raw_tables=[[["A", "B"]]],
            links=[DocumentLink(url="https://example.com/next", text="Next")],
            image_urls=["https://example.com/pic.jpg"],
            pdf_urls=[],
            raw_text="Raw body text",
        )

        extractor = ContentExtractor()
        extracted = extractor.extract(parsed)

        assert extracted.title == "Clean Title"
        assert len(extracted.paragraphs) == 2
        assert "core content" in extracted.cleaned_content
        assert len(extracted.tables) == 1


class TestPhase7Preprocessing:
    """Unit tests for Phase 7 (ContentPreprocessor & Hashing)."""

    def test_hashing_determinism(self):
        h1 = compute_content_hash("Hello World")
        h2 = compute_content_hash("Hello World")
        h3 = compute_content_hash("Different Text")
        assert h1 == h2
        assert h1 != h3
        assert len(h1) == 64

    def test_preprocessor_normalization_and_assembly(self):
        extracted = ExtractedContent(
            title="  My   Title  ",
            headings=["  Heading 1  "],
            paragraphs=["  Line 1  ", "  Line 2  "],
            tables=[[["X", "Y"]]],
            links=[DocumentLink(url="https://example.com/a", text="Link A")],
            image_urls=["https://example.com/img.png"],
            pdf_urls=["https://example.com/doc.pdf"],
            cleaned_content="  Paragraph one.\r\n\r\n\r\n\r\nParagraph two.  ",
        )

        preprocessor = ContentPreprocessor()
        doc = preprocessor.preprocess(
            extracted=extracted,
            job_id="JOB-123",
            url="https://example.com/page",
            crawl_depth=1,
        )

        assert doc.job_id == "JOB-123"
        assert doc.title == "My Title"
        assert doc.headings == ["Heading 1"]
        assert doc.content == "Paragraph one.\n\nParagraph two."
        assert len(doc.images) == 1
        assert doc.images[0].url == "https://example.com/img.png"
        assert len(doc.documents) == 1
        assert doc.documents[0].url == "https://example.com/doc.pdf"
        assert doc.metadata.content_hash == compute_content_hash(doc.content)
        assert doc.metadata.crawl_depth == 1


class TestPhase10JSONExport:
    """Unit tests for Phase 10 (JSONExporter)."""

    def test_export_job_results_atomic(self, tmp_path):
        preprocessor = ContentPreprocessor()
        extracted = ExtractedContent(
            title="Export Page",
            cleaned_content="Exportable text content",
        )
        doc = preprocessor.preprocess(
            extracted=extracted,
            job_id="JOB-EXP-1",
            url="https://example.com/export",
        )

        exporter = JSONExporter(base_output_dir=str(tmp_path))
        export_path = exporter.export_job_results(
            job_id="JOB-EXP-1",
            documents=[doc],
        )

        assert os.path.exists(export_path)
        with open(export_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["job_id"] == "JOB-EXP-1"
        assert data[0]["title"] == "Export Page"
        assert "content_hash" in data[0]["metadata"]
