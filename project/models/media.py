"""
Media ORM model.
Stores metadata for downloaded image and PDF binary files.
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
)
from sqlalchemy.orm import relationship
from project.config.database import Base


class Media(Base):
    __tablename__ = "media"

    media_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    page_id = Column(
        String(36),
        ForeignKey("pages.page_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    media_type = Column(String(32), nullable=False)  # "image" or "pdf"
    source_url = Column(Text, nullable=False)
    local_path = Column(Text, nullable=True)
    status = Column(String(32), default="pending", nullable=False)
    file_size = Column(Integer, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    page = relationship("Page", back_populates="media_items")
