"""
ScrapingJob ORM model.
Tracks job-level lifecycle, execution counters, and configuration parameters.
"""
import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Enum as SAEnum,
)
from sqlalchemy.orm import relationship
from project.config.database import Base


class JobStatus(str, enum.Enum):
    """Job lifecycle states matching Section 31 state machine."""
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"


class ScrapingJob(Base):
    __tablename__ = "scraping_jobs"

    job_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(
        SAEnum(JobStatus, name="job_status_enum", create_type=True),
        default=JobStatus.CREATED,
        nullable=False,
        index=True,
    )

    # Crawl Configuration Parameters (Section 28)
    crawl_depth = Column(Integer, default=2, nullable=False)
    recursive = Column(Boolean, default=True, nullable=False)
    javascript_fallback = Column(Boolean, default=True, nullable=False)
    robots_mode = Column(String(16), default="respect", nullable=False)
    timeout_seconds = Column(Integer, default=15, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    domain_rate_limit = Column(Float, default=2.0, nullable=False)
    max_concurrency = Column(Integer, default=3, nullable=False)

    # Operational Progress Counters (Section 28 & Wireframe 7.4)
    total_urls = Column(Integer, default=0, nullable=False)
    processed_urls = Column(Integer, default=0, nullable=False)
    successful_urls = Column(Integer, default=0, nullable=False)
    failed_urls = Column(Integer, default=0, nullable=False)
    skipped_urls = Column(Integer, default=0, nullable=False)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    url_records = relationship(
        "URLRecord",
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    error_logs = relationship(
        "ErrorLog",
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.job_id is None:
            self.job_id = str(uuid.uuid4())
        if self.status is None:
            self.status = JobStatus.CREATED
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.crawl_depth is None:
            self.crawl_depth = 2
        if self.recursive is None:
            self.recursive = True
        if self.javascript_fallback is None:
            self.javascript_fallback = True
        if self.robots_mode is None:
            self.robots_mode = "respect"
        if self.timeout_seconds is None:
            self.timeout_seconds = 15
        if self.max_retries is None:
            self.max_retries = 3
        if self.domain_rate_limit is None:
            self.domain_rate_limit = 2.0
        if self.max_concurrency is None:
            self.max_concurrency = 3
        if self.total_urls is None:
            self.total_urls = 0
        if self.processed_urls is None:
            self.processed_urls = 0
        if self.successful_urls is None:
            self.successful_urls = 0
        if self.failed_urls is None:
            self.failed_urls = 0
        if self.skipped_urls is None:
            self.skipped_urls = 0

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "status": self.status.value if isinstance(self.status, JobStatus) else self.status,
            "crawl_depth": self.crawl_depth,
            "recursive": self.recursive,
            "javascript_fallback": self.javascript_fallback,
            "robots_mode": self.robots_mode,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "domain_rate_limit": self.domain_rate_limit,
            "max_concurrency": self.max_concurrency,
            "total_urls": self.total_urls,
            "processed_urls": self.processed_urls,
            "successful_urls": self.successful_urls,
            "failed_urls": self.failed_urls,
            "skipped_urls": self.skipped_urls,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
