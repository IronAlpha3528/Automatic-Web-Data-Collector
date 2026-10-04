"""
JobManager service orchestrating job lifecycles and background execution.
Adheres to Section 31 (Job State Machine) and Section 46 (Complete Job Algorithm).
"""
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Set
from project.config.settings import CrawlConfig, settings
from project.schemas.job_schema import CreateJobRequest, JobResponse
from project.schemas.page_schema import ProcessedDocument
from project.models.job import ScrapingJob, JobStatus
from project.interfaces.storage import Storage
from project.services.storage import PostgresStorage
from project.services.crawler import Crawler
from project.services.json_exporter import JSONExporter
from project.services.error_manager import ErrorManager
from project.utils.url_normalizer import normalize_url, is_valid_url
from project.utils.logging import logger


class JobManager:
    """
    Manages job creation, background crawl tasks, state transitions,
    and automatic JSON dataset export upon completion.
    """

    def __init__(
        self,
        storage: Optional[PostgresStorage] = None,
        crawler: Optional[Crawler] = None,
        exporter: Optional[JSONExporter] = None,
    ):
        self.storage = storage or PostgresStorage()
        self.crawler = crawler or Crawler(storage=self.storage)
        self.exporter = exporter or JSONExporter()
        self._active_tasks: Dict[str, asyncio.Task] = {}

    async def create_job(self, request: CreateJobRequest) -> JobResponse:
        """
        Validates request and registers a new ScrapingJob in CREATED state.
        Pre-populates seed URLs into url_records.
        """
        job_id = str(uuid.uuid4())

        config = CrawlConfig(
            crawl_depth=request.crawl_depth,
            recursive=request.recursive,
            javascript_fallback=request.javascript_fallback,
            robots_mode=request.robots_mode,
            timeout_seconds=request.timeout_seconds,
            max_retries=request.max_retries,
            domain_rate_limit=request.domain_rate_limit,
            max_concurrency=request.max_concurrency,
        )

        # 1. Create job record in storage
        job = await self.storage.create_job(job_id, config)

        # 2. Normalize and queue seed URLs
        valid_seeds: List[str] = []
        for raw_url in request.seed_urls:
            url_str = str(raw_url)
            if is_valid_url(url_str):
                norm = normalize_url(url_str)
                rec = await self.storage.add_url(
                    job_id=job_id,
                    url=url_str,
                    normalized_url=norm,
                    depth=0,
                )
                if rec:
                    valid_seeds.append(url_str)

        if valid_seeds:
            await self.storage.update_job_counters(job_id, total_delta=len(valid_seeds))

        # Re-fetch updated job record
        updated_job = await self.storage.get_job(job_id)
        return JobResponse.model_validate(updated_job or job)

    async def start_job(self, job_id: str) -> JobResponse:
        """
        Transitions a job from CREATED to RUNNING and spawns the background crawl task.
        """
        job = await self.storage.get_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        if job.status not in (JobStatus.CREATED, JobStatus.FAILED):
            logger.warning(f"Job {job_id} is already in state {job.status}")
            return JobResponse.model_validate(job)

        # Transition to RUNNING
        await self.storage.update_job_status(
            job_id=job_id,
            status="RUNNING",
            started_at=datetime.now(timezone.utc),
        )

        # Launch background execution task
        task = asyncio.create_task(self._run_job(job_id))
        self._active_tasks[job_id] = task

        updated_job = await self.storage.get_job(job_id)
        return JobResponse.model_validate(updated_job)

    async def _run_job(self, job_id: str) -> None:
        """
        Internal worker running BFS traversal and finalizing state on completion.
        """
        try:
            job = await self.storage.get_job(job_id)
            if not job:
                return

            config = CrawlConfig(
                crawl_depth=job.crawl_depth,
                recursive=job.recursive,
                javascript_fallback=job.javascript_fallback,
                robots_mode=job.robots_mode,
                timeout_seconds=job.timeout_seconds,
                max_retries=job.max_retries,
                domain_rate_limit=job.domain_rate_limit,
                max_concurrency=job.max_concurrency,
            )

            # Fetch seed URLs
            url_records = await self.storage.get_url_records_by_job(job_id)
            seed_urls = [r.url for r in url_records if r.depth == 0]

            logger.info(f"Starting execution of job {job_id} with {len(seed_urls)} seeds")

            # Execute BFS crawl loop
            processed_docs = await self.crawler.crawl(
                job_id=job_id,
                seed_urls=seed_urls,
                config=config,
            )

            # Generate structured JSON dataset export (Phase 10)
            if processed_docs:
                try:
                    export_path = self.exporter.export_dataset(processed_docs, job_id)
                    logger.info(f"Generated JSON dataset export for job {job_id} at {export_path}")
                except Exception as exp_exc:
                    logger.error(f"Failed to export JSON dataset for job {job_id}: {exp_exc}")

            # Determine final state according to Section 46:
            # - No URL failures: COMPLETED
            # - Some URL failures: COMPLETED_WITH_ERRORS
            final_job = await self.storage.get_job(job_id)
            final_status = "COMPLETED"
            if final_job and final_job.failed_urls > 0:
                final_status = "COMPLETED_WITH_ERRORS"

            await self.storage.update_job_status(
                job_id=job_id,
                status=final_status,
                completed_at=datetime.now(timezone.utc),
            )
            logger.info(f"Job {job_id} finalized with status {final_status}")

        except asyncio.CancelledError:
            logger.warning(f"Job {job_id} was cancelled")
            await self.storage.update_job_status(
                job_id=job_id,
                status="FAILED",
                completed_at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            logger.critical(f"Catastrophic failure in job {job_id}: {exc}", exc_info=True)
            await self.storage.update_job_status(
                job_id=job_id,
                status="FAILED",
                completed_at=datetime.now(timezone.utc),
            )
        finally:
            self._active_tasks.pop(job_id, None)

    async def get_job(self, job_id: str) -> Optional[JobResponse]:
        """Fetches job details by ID."""
        job = await self.storage.get_job(job_id)
        return JobResponse.model_validate(job) if job else None

    async def list_jobs(self, limit: int = 50, offset: int = 0) -> List[JobResponse]:
        """Returns recent scraping jobs."""
        jobs = await self.storage.list_jobs(limit=limit, offset=offset)
        return [JobResponse.model_validate(j) for j in jobs]

    async def cancel_job(self, job_id: str) -> Optional[JobResponse]:
        """Cancels an active background crawl task if running."""
        task = self._active_tasks.get(job_id)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        job = await self.storage.get_job(job_id)
        return JobResponse.model_validate(job) if job else None
