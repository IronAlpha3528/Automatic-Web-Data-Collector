"""
URL tracking schemas and frontier contracts.
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel
from project.models.url_record import URLStatus


class CrawlURL(BaseModel):
    """Internal contract for URLs placed on the BFS queue frontier."""
    url: str
    normalized_url: str
    depth: int = 0
    parent_url_id: Optional[str] = None
    retry_count: int = 0


class URLRecordResponse(BaseModel):
    """Response DTO for URL record status queries."""
    url_id: str
    job_id: str
    url: str
    normalized_url: str
    depth: int
    status: URLStatus
    parent_url_id: Optional[str] = None
    discovered_at: datetime
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
