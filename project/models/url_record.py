"""
URLRecord ORM model.
Tracks every discovered URL, its crawl depth, parent lineage, and processing state.
"""
import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    ForeignKey,
    DateTime,
    Enum as SAEnum,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from project.config.database import Base


class URLStatus(str, enum.Enum):
    """URL lifecycle states matching Section 8."""
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class URLRecord(Base):
    __tablename__ = "url_records"

    url_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(
        String(36),
        ForeignKey("scraping_jobs.job_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url = Column(String(2048), nullable=False)
    normalized_url = Column(String(2048), nullable=False)
    depth = Column(Integer, default=0, nullable=False)
    status = Column(
        SAEnum(URLStatus, name="url_status_enum", create_type=False),
        default=URLStatus.QUEUED,
        nullable=False,
    )
    parent_url_id = Column(String(36), nullable=True)

    # Timestamps (Section 28)
    discovered_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    processing_completed_at = Column(DateTime(timezone=True), nullable=True)

    # Table constraints and indexes (Section 29)
    __table_args__ = (
        UniqueConstraint("job_id", "normalized_url", name="uq_job_normalized_url"),
        Index("ix_url_records_job_status", "job_id", "status"),
    )

    # Relationships
    job = relationship("ScrapingJob", back_populates="url_records")
    page = relationship(
        "Page",
        back_populates="url_record",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    error_logs = relationship(
        "ErrorLog",
        back_populates="url_record",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.url_id is None:
            self.url_id = str(uuid.uuid4())
        if self.status is None:
            self.status = URLStatus.QUEUED
        if self.discovered_at is None:
            self.discovered_at = datetime.now(timezone.utc)
        if self.depth is None:
            self.depth = 0
