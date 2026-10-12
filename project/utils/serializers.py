"""
Serializers and converters for translating between ORM entities and Pydantic schemas.
"""
from typing import List
from project.models.page import Page
from project.schemas.page_schema import ProcessedDocument, PageMetadata, DocumentLink, MediaReference


def page_to_processed_document(p: Page, default_status: str = "success") -> ProcessedDocument:
    """
    Losslessly converts a Page ORM instance (with url_record and media_items)
    to a fully populated ProcessedDocument schema conforming to Appendix B.
    """
    job_id = p.url_record.job_id if getattr(p, "url_record", None) else ""
    page_url = p.url_record.url if getattr(p, "url_record", None) else (p.title or "unknown")
    crawl_depth = p.url_record.depth if getattr(p, "url_record", None) and p.url_record.depth is not None else 0

    # Reconstruct document links
    links = [
        DocumentLink(url=l.get("url", ""), text=l.get("text", ""))
        for l in (p.links or [])
        if isinstance(l, dict)
    ]

    # Reconstruct media items (images and pdf documents)
    images: List[MediaReference] = []
    documents: List[MediaReference] = []
    if getattr(p, "media_items", None):
        for m in p.media_items:
            ref = MediaReference(
                url=m.source_url,
                local_path=m.local_path,
                media_type=m.media_type,
                file_size=m.file_size,
                status=m.status,
            )
            if m.media_type.lower() == "pdf":
                documents.append(ref)
            else:
                images.append(ref)

    return ProcessedDocument(
        job_id=job_id,
        url=page_url,
        title=p.title or "",
        headings=p.headings or [],
        paragraphs=p.paragraphs or [],
        content=p.content or "",
        tables=p.tables or [],
        links=links,
        images=images,
        documents=documents,
        metadata=PageMetadata(
            timestamp=p.processed_at.isoformat() if p.processed_at else (p.created_at.isoformat() if p.created_at else ""),
            crawl_depth=crawl_depth,
            content_hash=p.content_hash or "",
            status=default_status,
        ),
    )
