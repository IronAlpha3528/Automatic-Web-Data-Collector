"""
Job schemas for API requests, responses, and state tracking.
"""
from typing import List, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl
from project.models.job import JobStatus


class CreateJobRequest(BaseModel):
    """Payload to create a new scraping job (Section 8.2)."""
    seed_urls: List[HttpUrl] = Field(..., min_length=1, description="One or more seed URLs")
    crawl_depth: int = Field(default=2, ge=0, description="Max depth of link discovery")
    recursive: bool = Field(default=True, description="Enable recursive BFS link discovery")
    javascript_fallback: bool = Field(default=True, description="Enable Playwright fallback for dynamic pages")
    robots_mode: Literal["respect", "ignore"] = Field(default="respect", description="Robots.txt compliance mode")
    timeout_seconds: int = Field(default=15, gt=0, le=120, description="HTTP request timeout in seconds")
    max_retries: int = Field(default=3, ge=0, le=10, description="Max retry attempts for retryable failures")
    domain_rate_limit: float = Field(default=2.0, gt=0, description="Rate limit (requests/sec per domain)")
    max_concurrency: int = Field(default=3, gt=0, le=20, description="Global concurrency ceiling")


class JobResponse(BaseModel):
    """Job status and operational progress response."""
    job_id: str
    status: JobStatus
    crawl_depth: int
    recursive: bool
    javascript_fallback: bool
    robots_mode: str
    timeout_seconds: int
    max_retries: int
    domain_rate_limit: float
    max_concurrency: int
    total_urls: int
    processed_urls: int
    successful_urls: int
    failed_urls: int
    skipped_urls: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
