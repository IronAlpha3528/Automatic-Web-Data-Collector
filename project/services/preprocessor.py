"""
Content preprocessing module matching Phase 7 & Section 24 of Implementation Plan.
Performs conservative text normalization, boilerplate reduction, and creates ProcessedDocument.
"""
import re
import unicodedata
from datetime import datetime, timezone
from typing import List, Optional

from project.schemas.result_schema import ExtractedContent
from project.schemas.page_schema import ProcessedDocument, PageMetadata, MediaReference, DocumentLink
from project.utils.hashing import compute_content_hash
from project.utils.logging import logger


class ContentPreprocessor:
    """
    Preprocessor service performing conservative normalization and data assembly.
    Enforces Section 24 rules: no aggressive stemming, stopwords removal, or semantic altering.
    """

    def normalize_text(self, text: str) -> str:
        """
        Applies conservative text normalization:
        1. Unicode normalization (NFKC)
        2. Line-break normalization (\r\n -> \n)
        3. Collapses consecutive blank lines to max 2
        4. Strips leading/trailing line whitespace
        """
        if not text:
            return ""

        # 1. Unicode NFKC normalization
        normalized = unicodedata.normalize("NFKC", text)

        # 2. Line break standardisation
        normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

        # 3. Clean trailing whitespace per line
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in normalized.split("\n")]
        cleaned = "\n".join(lines)

        # 4. Collapse excessive blank lines
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    def preprocess(
        self,
        extracted: ExtractedContent,
        job_id: str,
        url: str,
        crawl_depth: int = 0,
        status: str = "success",
        timestamp: Optional[str] = None,
    ) -> ProcessedDocument:
        """
        Transforms ExtractedContent into a validated ProcessedDocument ready for persistence and export.
        """
        normalized_title = self.normalize_text(extracted.title)
        normalized_content = self.normalize_text(extracted.cleaned_content)
        
        normalized_headings: List[str] = [
            self.normalize_text(h) for h in extracted.headings if self.normalize_text(h)
        ]
        normalized_paragraphs: List[str] = [
            self.normalize_text(p) for p in extracted.paragraphs if self.normalize_text(p)
        ]

        # Assemble image and document media references
        images: List[MediaReference] = [
            MediaReference(url=img_url, media_type="image", status="pending")
            for img_url in extracted.image_urls
        ]
        documents: List[MediaReference] = [
            MediaReference(url=doc_url, media_type="pdf", status="pending")
            for doc_url in extracted.pdf_urls
        ]

        # Compute SHA-256 hash on normalized content
        content_hash = compute_content_hash(normalized_content)

        ts_str = timestamp or datetime.now(timezone.utc).isoformat()

        metadata = PageMetadata(
            timestamp=ts_str,
            crawl_depth=crawl_depth,
            content_hash=content_hash,
            status=status,
        )

        return ProcessedDocument(
            job_id=job_id,
            url=url,
            title=normalized_title,
            headings=normalized_headings,
            paragraphs=normalized_paragraphs,
            content=normalized_content,
            tables=extracted.tables,
            links=extracted.links,
            images=images,
            documents=documents,
            metadata=metadata,
        )
