"""
Page ORM model.
Stores processed textual content, title, SHA-256 hash, and structured extractions.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Text,
    ForeignKey,
    DateTime,
    JSON,
)
from sqlalchemy.orm import relationship
from project.config.database import Base


class Page(Base):
    __tablename__ = "pages"

    page_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    url_id = Column(
        String(36),
        ForeignKey("url_records.url_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    title = Column(String(512), nullable=True)
    content = Column(Text, nullable=True)
    content_hash = Column(String(64), nullable=True, index=True)

    # Structured extractions for Appendix B JSON serialization
    headings = Column(JSON, default=list, nullable=False)
    paragraphs = Column(JSON, default=list, nullable=False)
    tables = Column(JSON, default=list, nullable=False)
    links = Column(JSON, default=list, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    processed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    url_record = relationship("URLRecord", back_populates="page")
    media_items = relationship(
        "Media",
        back_populates="page",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
