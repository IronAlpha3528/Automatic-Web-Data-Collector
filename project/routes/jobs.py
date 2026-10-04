"""
Jobs REST API routes conforming to Section 34.
Handles job creation, listing, status inspection, and execution launch.
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status
from project.schemas.job_schema import CreateJobRequest, JobResponse
from project.services.job_manager import JobManager
from project.services.storage import PostgresStorage

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])

# Singleton manager instance for API requests
_job_manager: Optional[JobManager] = None

def get_job_manager() -> JobManager:
    global _job_manager
    if _job_manager is None:
        storage = PostgresStorage()
        _job_manager = JobManager(storage=storage)
    return _job_manager


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_scraping_job(
    request: CreateJobRequest,
    manager: JobManager = Depends(get_job_manager),
) -> JobResponse:
    """Creates a new scraping job in CREATED state."""
    try:
        return await manager.create_job(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create job: {str(exc)}",
        )


@router.get("", response_model=List[JobResponse])
async def list_scraping_jobs(
    limit: int = 50,
    offset: int = 0,
    manager: JobManager = Depends(get_job_manager),
) -> List[JobResponse]:
    """Lists recent scraping jobs."""
    return await manager.list_jobs(limit=limit, offset=offset)


@router.get("/{job_id}", response_model=JobResponse)
async def get_scraping_job(
    job_id: str,
    manager: JobManager = Depends(get_job_manager),
) -> JobResponse:
    """Retrieves operational details and counters for a specific job."""
    job = await manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )
    return job


@router.post("/{job_id}/start", response_model=JobResponse)
async def start_scraping_job(
    job_id: str,
    manager: JobManager = Depends(get_job_manager),
) -> JobResponse:
    """Triggers asynchronous crawl execution for a created job."""
    try:
        return await manager.start_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting job: {str(exc)}",
        )


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_scraping_job(
    job_id: str,
    manager: JobManager = Depends(get_job_manager),
) -> JobResponse:
    """Cancels an active scraping job."""
    job = await manager.cancel_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )
    return job
