"""
Errors REST API router conforming to Section 34.
"""
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, status
from project.services.storage import PostgresStorage

router = APIRouter(prefix="/api/jobs", tags=["Errors"])

def get_storage() -> PostgresStorage:
    return PostgresStorage()


@router.get("/{job_id}/errors")
async def get_job_errors(
    job_id: str,
    storage: PostgresStorage = Depends(get_storage),
) -> Dict[str, Any]:
    """Retrieves all categorized error logs for a scraping job."""
    job = await storage.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    errors = await storage.get_errors_by_job(job_id)
    return {
        "job_id": job_id,
        "total_errors": len(errors),
        "errors": [
            {
                "error_id": e.error_id,
                "url_id": e.url_id,
                "error_type": e.error_type,
                "message": e.message,
                "attempt": e.attempt,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            }
            for e in errors
        ],
    }
