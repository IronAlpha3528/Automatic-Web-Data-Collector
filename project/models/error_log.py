"""
ErrorLog ORM model.
Tracks categorized processing errors with retry attempt context.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    ForeignKey,
    DateTime,
    Index,
)
from sqlalchemy.orm import relationship
from project.config.database import Base


class ErrorLog(Base):
    __tablename__ = "error_logs"

    error_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(
        String(36),
        ForeignKey("scraping_jobs.job_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url_id = Column(
        String(36),
        ForeignKey("url_records.url_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    error_type = Column(String(64), nullable=False, index=True)
    message = Column(Text, nullable=True)
    attempt = Column(Integer, default=1, nullable=False)
    timestamp = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_error_logs_job_type", "job_id", "error_type"),
    )

    # Relationships
    job = relationship("ScrapingJob", back_populates="error_logs")
    url_record = relationship("URLRecord", back_populates="error_logs")
