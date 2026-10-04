"""
Phase 1 Foundation Unit Verification Tests.
Validates Settings, Database Models, Schemas, Protocols, and Exceptions.
"""
import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.schema import CreateTable

from project.config.settings import Settings, CrawlConfig, settings
from project.config.database import Base, engine
from project.models import (
    ScrapingJob,
    JobStatus,
    URLRecord,
    URLStatus,
    Page,
    Media,
    ErrorLog,
)
from project.schemas import (
    CreateJobRequest,
    JobResponse,
    CrawlURL,
    ProcessedDocument,
    PageMetadata,
    DocumentLink,
    MediaReference,
    RetrievalResult,
    ParsedDocument,
    ExtractedContent,
    URLProcessingResult,
    ProcessingError,
)
from project.interfaces import (
    Retriever,
    Renderer,
    Parser,
    Extractor,
    Storage,
    MediaDownloader,
)
from project.utils import (
    ProjectError,
    RetrievalError,
    TimeoutError,
    HTTPError,
    logger,
)


class TestSettings:
    """Validates configuration baseline and helper methods."""

    def test_default_crawl_config_baseline(self):
        cfg = settings.get_default_crawl_config()
        assert cfg.crawl_depth == 2
        assert cfg.recursive is True
        assert cfg.javascript_fallback is True
        assert cfg.robots_mode == "respect"
        assert cfg.timeout_seconds == 15
        assert cfg.max_retries == 3
        assert cfg.domain_rate_limit == 2.0
        assert cfg.max_concurrency == 3

    def test_async_database_url_normalization(self):
        s1 = Settings(database_url="postgresql://user:pass@localhost:5432/testdb")
        assert s1.get_async_database_url() == "postgresql+asyncpg://user:pass@localhost:5432/testdb"

        s2 = Settings(database_url="postgres://user:pass@localhost:5432/testdb")
        assert s2.get_async_database_url() == "postgresql+asyncpg://user:pass@localhost:5432/testdb"

        s3 = Settings(database_url="postgresql+asyncpg://user:pass@localhost:5432/testdb")
        assert s3.get_async_database_url() == "postgresql+asyncpg://user:pass@localhost:5432/testdb"

    def test_crawl_config_validation(self):
        with pytest.raises(PydanticValidationError):
            # timeout cannot be <= 0
            CrawlConfig(timeout_seconds=-1)

        with pytest.raises(PydanticValidationError):
            # max_retries cannot be negative
            CrawlConfig(max_retries=-1)


class TestDatabaseModels:
    """Validates ORM models, table definitions, foreign keys, and DDL compilation."""

    def test_all_five_tables_registered(self):
        table_names = set(Base.metadata.tables.keys())
        expected = {"scraping_jobs", "url_records", "pages", "media", "error_logs"}
        assert expected.issubset(table_names), f"Missing tables: {expected - table_names}"

    def test_schema_ddl_compilation(self):
        """Compiles DDL for each table to verify schema syntax and constraint validity."""
        for table in Base.metadata.sorted_tables:
            ddl = str(CreateTable(table).compile(engine))
            assert len(ddl) > 0
            assert table.name in ddl

    def test_unique_constraint_on_url_records(self):
        table = Base.metadata.tables["url_records"]
        uq_names = [uq.name for uq in table.constraints if hasattr(uq, "name") and uq.name]
        assert "uq_job_normalized_url" in uq_names

    def test_model_instantiation(self):
        job = ScrapingJob(job_id="test-job-001", crawl_depth=3)
        assert job.status == JobStatus.CREATED
        assert job.crawl_depth == 3
        d = job.to_dict()
        assert d["job_id"] == "test-job-001"
        assert d["status"] == "CREATED"


class TestSchemasAndContracts:
    """Validates data contracts for inter-module communication."""

    def test_create_job_request_valid(self):
        req = CreateJobRequest(
            seed_urls=["https://example.com/start"],
            crawl_depth=2,
            robots_mode="respect",
        )
        assert len(req.seed_urls) == 1
        assert str(req.seed_urls[0]) == "https://example.com/start"

    def test_create_job_request_invalid_url(self):
        with pytest.raises(PydanticValidationError):
            CreateJobRequest(seed_urls=["not-a-valid-url"])

    def test_appendix_b_processed_document_schema(self):
        doc = ProcessedDocument(
            job_id="JOB-001",
            url="https://example.com/article",
            title="Example Article",
            headings=["Intro", "Body"],
            paragraphs=["P1 text", "P2 text"],
            content="Combined text content",
            tables=[[["Header 1", "Header 2"], ["Val 1", "Val 2"]]],
            links=[DocumentLink(url="https://example.com/page2", text="Next Page")],
            images=[MediaReference(url="https://example.com/img.jpg", local_path="images/001.jpg")],
            documents=[MediaReference(url="https://example.com/doc.pdf", local_path="pdfs/001.pdf", media_type="pdf")],
            metadata=PageMetadata(
                timestamp="2026-10-04T12:00:00Z",
                crawl_depth=1,
                content_hash="abc123sha256",
                status="success",
            ),
        )
        dump = doc.model_dump()
        assert dump["job_id"] == "JOB-001"
        assert dump["metadata"]["content_hash"] == "abc123sha256"
        assert len(dump["headings"]) == 2
        assert len(dump["links"]) == 1

    def test_pipeline_contracts_instantiation(self):
        res = RetrievalResult(
            url="https://example.com",
            status_code=200,
            content="<html><body>Hello</body></html>",
            content_type="text/html",
            success=True,
        )
        assert res.success is True
        assert res.status_code == 200

        parsed = ParsedDocument(
            url="https://example.com",
            title="Test",
            headings=["H1"],
            paragraphs=["P1"],
            raw_text="Test H1 P1",
        )
        assert parsed.title == "Test"

        extracted = ExtractedContent(
            title="Test",
            cleaned_content="Test H1 P1",
        )
        assert extracted.cleaned_content == "Test H1 P1"

        proc_res = URLProcessingResult(
            url="https://example.com",
            status="SUCCESS",
            discovered_links=["https://example.com/child"],
        )
        assert len(proc_res.discovered_links) == 1


class TestProtocolsAndExceptions:
    """Validates Dependency Inversion protocols and custom exceptions."""

    def test_protocols_exist_and_runtime_checkable(self):
        assert isinstance(Retriever, type)
        assert isinstance(Renderer, type)
        assert isinstance(Parser, type)
        assert isinstance(Extractor, type)
        assert isinstance(Storage, type)
        assert isinstance(MediaDownloader, type)

    def test_exception_inheritance(self):
        te = TimeoutError("Request timed out")
        assert isinstance(te, RetrievalError)
        assert isinstance(te, ProjectError)
        assert isinstance(te, Exception)

        he = HTTPError("Not Found", status_code=404)
        assert he.status_code == 404
        assert isinstance(he, RetrievalError)

    def test_logger_functionality(self):
        logger.info("Foundation test log message - operational check.")
        assert logger.name == "web_data_acq"
