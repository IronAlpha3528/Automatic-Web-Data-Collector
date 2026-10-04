"""
Inter-stage typed pipeline contracts and error definitions.
Enforces Rule 6 (Explicit Data Contracts) across processing stages.
"""
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from project.schemas.page_schema import DocumentLink, MediaReference, ProcessedDocument


class ProcessingError(BaseModel):
    """Categorized error record matching Section 14 error taxonomy."""
    category: str
    message: str
    attempt: int = 1
    recoverable: bool = False


class RetrievalResult(BaseModel):
    """Output from HTTPX retriever or Playwright renderer."""
    url: str
    status_code: Optional[int] = None
    content: Optional[Union[bytes, str]] = None
    content_type: Optional[str] = None
    success: bool
    is_rendered: bool = False
    error: Optional[ProcessingError] = None


class ParsedDocument(BaseModel):
    """Output from HTML/PDF parser."""
    url: str
    title: Optional[str] = None
    headings: List[str] = Field(default_factory=list)
    paragraphs: List[str] = Field(default_factory=list)
    raw_tables: List[Any] = Field(default_factory=list)
    links: List[DocumentLink] = Field(default_factory=list)
    image_urls: List[str] = Field(default_factory=list)
    pdf_urls: List[str] = Field(default_factory=list)
    raw_text: str = ""


class ExtractedContent(BaseModel):
    """Output from content extractor (primary content isolated from noise)."""
    title: str = ""
    headings: List[str] = Field(default_factory=list)
    paragraphs: List[str] = Field(default_factory=list)
    tables: List[Any] = Field(default_factory=list)
    links: List[DocumentLink] = Field(default_factory=list)
    image_urls: List[str] = Field(default_factory=list)
    pdf_urls: List[str] = Field(default_factory=list)
    cleaned_content: str = ""


class URLProcessingResult(BaseModel):
    """
    Contract returned by URL processing pipeline to the Crawler (Section 44).
    """
    url: str
    status: str
    page: Optional[ProcessedDocument] = None
    discovered_links: List[str] = Field(default_factory=list)
    media: List[MediaReference] = Field(default_factory=list)
    error: Optional[ProcessingError] = None
