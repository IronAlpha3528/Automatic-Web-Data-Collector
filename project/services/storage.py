"""
PostgresStorage implementation using SQLAlchemy 2.0 AsyncSession.
Conforms to project.interfaces.storage.Storage protocol.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from project.config.database import AsyncSessionLocal
from project.models.job import ScrapingJob, JobStatus
from project.models.url_record import URLRecord, URLStatus
from project.models.page import Page
from project.models.media import Media
from project.models.error_log import ErrorLog
from project.schemas.job_schema import CreateJobRequest
from project.schemas.url_schema import CrawlURL
from project.schemas.page_schema import ProcessedDocument, MediaReference
from project.schemas.result_schema import ProcessingError
from project.config.settings import CrawlConfig
from project.utils.logging import logger


class PostgresStorage:
    """
    Asynchronous PostgreSQL storage engine coordinating database transactions.
    Decoupled from crawling logic; provides atomic boundaries for persistence.
    """

    def __init__(self, session_factory: Optional[async_sessionmaker[AsyncSession]] = None):
        self.session_factory = session_factory or AsyncSessionLocal

    async def create_job(self, job_id: str, config: CrawlConfig) -> ScrapingJob:
        """Persists a new ScrapingJob record with configuration parameters."""
        async with self.session_factory() as session:
            async with session.begin():
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
                    created_at=datetime.now(timezone.utc),
                )
                session.add(job)
            return job

    async def get_job(self, job_id: str) -> Optional[ScrapingJob]:
        """Retrieves a ScrapingJob by ID."""
        async with self.session_factory() as session:
            stmt = select(ScrapingJob).where(ScrapingJob.job_id == job_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_jobs(self, limit: int = 50, offset: int = 0) -> List[ScrapingJob]:
        """Retrieves recent ScrapingJobs ordered by creation time descending."""
        async with self.session_factory() as session:
            stmt = (
                select(ScrapingJob)
                .order_by(ScrapingJob.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def update_job_status(
        self,
        job_id: str,
        status: str,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> None:
        """Transitions job lifecycle status and optional lifecycle timestamps."""
        async with self.session_factory() as session:
            async with session.begin():
                values: Dict[str, Any] = {"status": JobStatus(status)}
                if started_at is not None:
                    values["started_at"] = started_at
                if completed_at is not None:
                    values["completed_at"] = completed_at

                stmt = (
                    update(ScrapingJob)
                    .where(ScrapingJob.job_id == job_id)
                    .values(**values)
                )
                await session.execute(stmt)

    async def update_job_counters(
        self,
        job_id: str,
        total_delta: int = 0,
        processed_delta: int = 0,
        successful_delta: int = 0,
        failed_delta: int = 0,
        skipped_delta: int = 0,
    ) -> None:
        """Atomically increments or updates operational progress counters."""
        async with self.session_factory() as session:
            async with session.begin():
                stmt = (
                    update(ScrapingJob)
                    .where(ScrapingJob.job_id == job_id)
                    .values(
                        total_urls=ScrapingJob.total_urls + total_delta,
                        processed_urls=ScrapingJob.processed_urls + processed_delta,
                        successful_urls=ScrapingJob.successful_urls + successful_delta,
                        failed_urls=ScrapingJob.failed_urls + failed_delta,
                        skipped_urls=ScrapingJob.skipped_urls + skipped_delta,
                    )
                )
                await session.execute(stmt)

    async def add_url(
        self,
        job_id: str,
        url: str,
        normalized_url: str,
        depth: int = 0,
        parent_url_id: Optional[str] = None,
    ) -> Optional[URLRecord]:
        """
        Inserts a single discovered URL into url_records.
        Returns the created record, or None if already exists for this job.
        """
        async with self.session_factory() as session:
            async with session.begin():
                # Check duplicate within this job
                stmt = select(URLRecord).where(
                    URLRecord.job_id == job_id,
                    URLRecord.normalized_url == normalized_url,
                )
                existing = (await session.execute(stmt)).scalar_one_or_none()
                if existing:
                    return None

                record = URLRecord(
                    url_id=str(uuid.uuid4()),
                    job_id=job_id,
                    url=url,
                    normalized_url=normalized_url,
                    depth=depth,
                    status=URLStatus.QUEUED,
                    parent_url_id=parent_url_id,
                    discovered_at=datetime.now(timezone.utc),
                )
                session.add(record)
            return record

    async def get_url_record(self, job_id: str, normalized_url: str) -> Optional[URLRecord]:
        """Retrieves a URLRecord by job_id and normalized_url."""
        async with self.session_factory() as session:
            stmt = select(URLRecord).where(
                URLRecord.job_id == job_id,
                URLRecord.normalized_url == normalized_url,
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def update_url_status(
        self,
        job_id: str,
        normalized_url: str,
        status: str,
    ) -> None:
        """Updates the status of a specific URLRecord."""
        async with self.session_factory() as session:
            async with session.begin():
                values: Dict[str, Any] = {"status": URLStatus(status)}
                if status == "PROCESSING":
                    values["processing_started_at"] = datetime.now(timezone.utc)
                elif status in ("SUCCESS", "FAILED", "SKIPPED"):
                    values["processing_completed_at"] = datetime.now(timezone.utc)

                stmt = (
                    update(URLRecord)
                    .where(
                        URLRecord.job_id == job_id,
                        URLRecord.normalized_url == normalized_url,
                    )
                    .values(**values)
                )
                await session.execute(stmt)

    async def save_page(self, page: ProcessedDocument) -> None:
        """
        Persists extracted Page content, headings, paragraphs, tables, links,
        and associated Media metadata in an atomic transaction.
        """
        async with self.session_factory() as session:
            async with session.begin():
                # 1. Fetch matching URLRecord
                stmt = select(URLRecord).where(
                    URLRecord.job_id == page.job_id,
                    URLRecord.url == page.url,
                )
                url_rec = (await session.execute(stmt)).scalar_one_or_none()

                if not url_rec:
                    # If not matched by exact URL, try normalized URL
                    stmt = select(URLRecord).where(
                        URLRecord.job_id == page.job_id,
                    )
                    records = (await session.execute(stmt)).scalars().all()
                    # Find matching record
                    for r in records:
                        if r.url == page.url:
                            url_rec = r
                            break

                if not url_rec:
                    # Create placeholder URLRecord if not found
                    url_rec = URLRecord(
                        url_id=str(uuid.uuid4()),
                        job_id=page.job_id,
                        url=page.url,
                        normalized_url=page.url,
                        depth=page.metadata.crawl_depth,
                        status=URLStatus.SUCCESS,
                        discovered_at=datetime.now(timezone.utc),
                        processing_started_at=datetime.now(timezone.utc),
                        processing_completed_at=datetime.now(timezone.utc),
                    )
                    session.add(url_rec)
                    await session.flush()

                # 2. Check if page already exists for this url_id
                page_stmt = select(Page).where(Page.url_id == url_rec.url_id)
                existing_page = (await session.execute(page_stmt)).scalar_one_or_none()

                # Convert structured data to serializable dictionaries/lists
                links_data = [{"url": l.url, "text": l.text} for l in page.links]

                if existing_page:
                    existing_page.title = page.title
                    existing_page.content = page.content
                    existing_page.content_hash = page.metadata.content_hash
                    existing_page.headings = page.headings
                    existing_page.paragraphs = page.paragraphs
                    existing_page.tables = page.tables
                    existing_page.links = links_data
                    existing_page.processed_at = datetime.now(timezone.utc)
                    page_id = existing_page.page_id
                else:
                    page_id = str(uuid.uuid4())
                    db_page = Page(
                        page_id=page_id,
                        url_id=url_rec.url_id,
                        title=page.title,
                        content=page.content,
                        content_hash=page.metadata.content_hash,
                        headings=page.headings,
                        paragraphs=page.paragraphs,
                        tables=page.tables,
                        links=links_data,
                        created_at=datetime.now(timezone.utc),
                        processed_at=datetime.now(timezone.utc),
                    )
                    session.add(db_page)

                # 3. Add Media references (Images + Documents)
                all_media = list(page.images) + list(page.documents)
                for item in all_media:
                    media_rec = Media(
                        media_id=str(uuid.uuid4()),
                        page_id=page_id,
                        media_type=item.media_type,
                        source_url=item.url,
                        local_path=item.local_path,
                        status=item.status,
                        file_size=item.file_size,
                        created_at=datetime.now(timezone.utc),
                    )
                    session.add(media_rec)

    async def record_error(
        self,
        job_id: str,
        url_id: Optional[str],
        error: ProcessingError,
    ) -> None:
        """Records an error into the error_logs table."""
        async with self.session_factory() as session:
            async with session.begin():
                err = ErrorLog(
                    error_id=str(uuid.uuid4()),
                    job_id=job_id,
                    url_id=url_id,
                    error_type=error.category,
                    message=error.message,
                    attempt=error.attempt,
                    timestamp=datetime.now(timezone.utc),
                )
                session.add(err)

    async def get_pages_by_job(self, job_id: str) -> List[Page]:
        """Retrieves all Page records associated with a scraping job."""
        async with self.session_factory() as session:
            stmt = (
                select(Page)
                .options(selectinload(Page.url_record))
                .join(URLRecord, Page.url_id == URLRecord.url_id)
                .where(URLRecord.job_id == job_id)
                .order_by(Page.created_at.asc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_errors_by_job(self, job_id: str) -> List[ErrorLog]:
        """Retrieves all ErrorLog records for a scraping job."""
        async with self.session_factory() as session:
            stmt = (
                select(ErrorLog)
                .where(ErrorLog.job_id == job_id)
                .order_by(ErrorLog.timestamp.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_url_records_by_job(self, job_id: str) -> List[URLRecord]:
        """Retrieves all URL records for a job."""
        async with self.session_factory() as session:
            stmt = (
                select(URLRecord)
                .where(URLRecord.job_id == job_id)
                .order_by(URLRecord.discovered_at.asc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
