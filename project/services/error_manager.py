"""
ErrorManager service for error categorization, recording, and fault isolation.
Enforces Section 14 (Error Taxonomy) and Section 17 (Error Manager).
"""
from typing import Optional, Any
from project.schemas.result_schema import ProcessingError
from project.interfaces.storage import Storage
from project.utils.exceptions import (
    ValidationError,
    NetworkError,
    TimeoutError,
    HTTPError,
    ParsingError,
    ExtractionError,
    RenderingError,
    MediaError,
    PersistenceError,
)
from project.utils.logging import logger


class ErrorManager:
    """
    Classifies, logs, and persists errors into database storage while
    ensuring URL-level failure isolation.
    """

    def __init__(self, storage: Optional[Storage] = None):
        self.storage = storage

    def classify_exception(self, exc: Exception, attempt: int = 1) -> ProcessingError:
        """
        Maps an arbitrary or domain exception to a standardized ProcessingError.
        """
        if isinstance(exc, TimeoutError):
            return ProcessingError(
                category="TIMEOUT_ERROR",
                message=str(exc),
                attempt=attempt,
                recoverable=True,
            )
        if isinstance(exc, NetworkError):
            return ProcessingError(
                category="NETWORK_ERROR",
                message=str(exc),
                attempt=attempt,
                recoverable=True,
            )
        if isinstance(exc, HTTPError):
            recoverable = exc.status_code in (429, 500, 502, 503, 504)
            return ProcessingError(
                category="HTTP_ERROR",
                message=f"HTTP {exc.status_code}: {exc.message}",
                attempt=attempt,
                recoverable=recoverable,
            )
        if isinstance(exc, ValidationError):
            return ProcessingError(
                category="URL_VALIDATION_ERROR",
                message=str(exc),
                attempt=attempt,
                recoverable=False,
            )
        if isinstance(exc, ParsingError):
            return ProcessingError(
                category="PARSING_ERROR",
                message=str(exc),
                attempt=attempt,
                recoverable=False,
            )
        if isinstance(exc, ExtractionError):
            return ProcessingError(
                category="EXTRACTION_ERROR",
                message=str(exc),
                attempt=attempt,
                recoverable=False,
            )
        if isinstance(exc, RenderingError):
            return ProcessingError(
                category="JS_RENDERING_ERROR",
                message=str(exc),
                attempt=attempt,
                recoverable=False,
            )
        if isinstance(exc, MediaError):
            return ProcessingError(
                category="MEDIA_DOWNLOAD_ERROR",
                message=str(exc),
                attempt=attempt,
                recoverable=False,
            )
        if isinstance(exc, PersistenceError):
            return ProcessingError(
                category="DATABASE_ERROR",
                message=str(exc),
                attempt=attempt,
                recoverable=False,
            )

        # Fallback classification based on exception type name or message
        exc_name = type(exc).__name__.lower()
        if "timeout" in exc_name:
            return ProcessingError(category="TIMEOUT_ERROR", message=str(exc), attempt=attempt, recoverable=True)
        if "connect" in exc_name or "network" in exc_name:
            return ProcessingError(category="NETWORK_ERROR", message=str(exc), attempt=attempt, recoverable=True)
        if "parse" in exc_name or "xml" in exc_name or "html" in exc_name:
            return ProcessingError(category="PARSING_ERROR", message=str(exc), attempt=attempt, recoverable=False)

        return ProcessingError(
            category="UNKNOWN_ERROR",
            message=f"{type(exc).__name__}: {str(exc)}",
            attempt=attempt,
            recoverable=False,
        )

    async def record(
        self,
        job_id: str,
        error: ProcessingError,
        url_id: Optional[str] = None,
    ) -> None:
        """
        Logs and persists the error to storage.
        Guarantees that a recording failure does not crash the application.
        """
        logger.error(
            f"[{job_id}] [{error.category}] (Attempt {error.attempt}): {error.message}"
        )

        if self.storage:
            try:
                await self.storage.record_error(
                    job_id=job_id,
                    url_id=url_id,
                    error=error,
                )
            except Exception as store_exc:
                logger.critical(
                    f"Failed to persist error record to storage: {store_exc}"
                )

    def is_job_terminating_failure(self, error: ProcessingError) -> bool:
        """
        Section 70 (Golden Failure-Handling Rule):
        Only unrecoverable persistence/system failures terminate the entire job.
        Individual page or retrieval failures never abort the job.
        """
        return error.category in ("DATABASE_ERROR", "SYSTEM_ABORT")
