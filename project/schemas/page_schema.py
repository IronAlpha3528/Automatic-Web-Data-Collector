"""
Document and media schemas conforming to Appendix B representative JSON schema.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class DocumentLink(BaseModel):
    url: str
    text: str


class MediaReference(BaseModel):
    url: str
    local_path: Optional[str] = None
    media_type: str = "image"
    file_size: Optional[int] = None
    status: str = "pending"


class PageMetadata(BaseModel):
    timestamp: str
    crawl_depth: int
    content_hash: str
    status: str = "success"


class ProcessedDocument(BaseModel):
    """
    Structured document model conforming directly to Design Document Appendix B.
    """
    job_id: str
    url: str
    title: str = ""
    headings: List[str] = Field(default_factory=list)
    paragraphs: List[str] = Field(default_factory=list)
    content: str = ""
    tables: List[Any] = Field(default_factory=list)
    links: List[DocumentLink] = Field(default_factory=list)
    images: List[MediaReference] = Field(default_factory=list)
    documents: List[MediaReference] = Field(default_factory=list)
    metadata: PageMetadata
