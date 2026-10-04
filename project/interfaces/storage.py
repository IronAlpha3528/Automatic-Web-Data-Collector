"""
Storage interface protocol for database persistence.
Allows the Crawler and JobManager to persist state without knowing the database schema.
"""
from typing import Protocol, runtime_checkable, Optional, List
from project.schemas.page_schema import ProcessedDocument, MediaReference
from project.schemas.result_schema import ProcessingError
from project.schemas.job_schema import JobResponse


@runtime_checkable
class Storage(Protocol):
    """Abstract persistence protocol enforcing Rule 2 (Low Coupling)."""

    async def save_page(self, page: ProcessedDocument) -> None:
        """Persists extracted page content, metadata, and media references."""
        ...

    async def update_url_status(
        self,
        job_id: str,
        normalized_url: str,
        status: str,
    ) -> None:
        """Updates the status of a specific URLRecord."""
        ...

    async def record_error(
        self,
        job_id: str,
        url_id: Optional[str],
        error: ProcessingError,
    ) -> None:
        """Records an error into the error_logs table."""
        ...

    async def update_job_counters(
        self,
        job_id: str,
        total_delta: int = 0,
        processed_delta: int = 0,
        successful_delta: int = 0,
        failed_delta: int = 0,
        skipped_delta: int = 0,
    ) -> None:
        """Atomically updates job-level counters."""
        ...

    async def update_job_status(self, job_id: str, status: str) -> None:
        """Transitions job lifecycle status."""
        ...
