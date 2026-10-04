"""
Results and Export REST API routes conforming to Section 34.
"""
from pathlib import Path
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import FileResponse
from project.services.storage import PostgresStorage
from project.services.json_exporter import JSONExporter
from project.config.settings import settings

router = APIRouter(prefix="/api/jobs", tags=["Results"])

def get_storage() -> PostgresStorage:
    return PostgresStorage()


@router.get("/{job_id}/results")
async def get_job_results(
    job_id: str,
    storage: PostgresStorage = Depends(get_storage),
) -> Dict[str, Any]:
    """Retrieves processed document results and summaries for a job."""
    job = await storage.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    pages = await storage.get_pages_by_job(job_id)
    results = []
    for p in pages:
        results.append({
            "page_id": p.page_id,
            "title": p.title,
            "content_hash": p.content_hash,
            "content_preview": (p.content[:300] + "...") if p.content and len(p.content) > 300 else p.content,
            "headings_count": len(p.headings) if p.headings else 0,
            "paragraphs_count": len(p.paragraphs) if p.paragraphs else 0,
            "tables_count": len(p.tables) if p.tables else 0,
            "links_count": len(p.links) if p.links else 0,
            "processed_at": p.processed_at.isoformat() if p.processed_at else None,
        })

    return {
        "job_id": job_id,
        "total_results": len(results),
        "results": results,
    }


@router.get("/{job_id}/export")
async def export_job_dataset(
    job_id: str,
    storage: PostgresStorage = Depends(get_storage),
):
    """
    Downloads the Appendix B compliant structured JSON dataset export.
    """
    job = await storage.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    export_path = Path(settings.output_dir) / "jobs" / job_id / "json" / f"{job_id}_results.json"

    if not export_path.exists():
        # Generate on-the-fly if not already written
        pages = await storage.get_pages_by_job(job_id)
        if not pages:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No processed records found to export for job: {job_id}",
            )

        # Convert ORM pages to ProcessedDocument models
        from project.schemas.page_schema import ProcessedDocument, PageMetadata, DocumentLink
        docs = []
        for p in pages:
            page_url = p.url_record.url if getattr(p, "url_record", None) else (p.title or "unknown")
            doc = ProcessedDocument(
                job_id=job_id,
                url=page_url,
                title=p.title or "",
                headings=p.headings or [],
                paragraphs=p.paragraphs or [],
                content=p.content or "",
                tables=p.tables or [],
                links=[DocumentLink(url=l.get("url", ""), text=l.get("text", "")) for l in (p.links or [])],
                images=[],
                documents=[],
                metadata=PageMetadata(
                    timestamp=p.processed_at.isoformat() if p.processed_at else "",
                    crawl_depth=0,
                    content_hash=p.content_hash or "",
                    status="success",
                ),
            )
            docs.append(doc)

        exporter = JSONExporter()
        export_path = exporter.export_dataset(docs, job_id)

    return FileResponse(
        path=export_path,
        media_type="application/json",
        filename=f"dataset_{job_id}.json",
    )
