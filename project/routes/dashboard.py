"""
Web UI dashboard routes using Jinja2 templates.
Implements the Presentation layer conforming to Section 7 of the Design Document.
"""
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Request, Form, Depends, HTTPException, responses, status
from fastapi.templating import Jinja2Templates

from project.schemas.job_schema import CreateJobRequest
from project.services.job_manager import JobManager
from project.routes.jobs import get_job_manager

template_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(template_dir))

router = APIRouter(include_in_schema=False)


@router.get("/")
async def dashboard_view(
    request: Request,
    manager: JobManager = Depends(get_job_manager),
):
    """Main dashboard showing recent scraping jobs."""
    jobs = await manager.list_jobs(limit=50)
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "jobs": [j.model_dump() for j in jobs],
            "active_tab": "dashboard",
        },
    )


@router.get("/jobs/new")
async def create_job_view(request: Request):
    """Job creation form matching Section 7.3 wireframe."""
    return templates.TemplateResponse(
        request=request,
        name="create_job.html",
        context={"active_tab": "create"},
    )


@router.post("/jobs")
async def create_and_start_job_form(
    request: Request,
    seed_urls: str = Form(...),
    crawl_depth: int = Form(2),
    timeout_seconds: int = Form(15),
    max_retries: int = Form(3),
    domain_rate_limit: float = Form(2.0),
    max_concurrency: int = Form(3),
    robots_mode: str = Form("respect"),
    recursive: bool = Form(False),
    javascript_fallback: bool = Form(False),
    manager: JobManager = Depends(get_job_manager),
):
    """Handles web form submission, creates the job, starts it, and redirects to monitor."""
    urls = [u.strip() for u in seed_urls.splitlines() if u.strip()]
    if not urls:
        raise HTTPException(status_code=400, detail="At least one seed URL is required")

    job_req = CreateJobRequest(
        seed_urls=urls,
        crawl_depth=crawl_depth,
        recursive=recursive,
        javascript_fallback=javascript_fallback,
        robots_mode=robots_mode,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        domain_rate_limit=domain_rate_limit,
        max_concurrency=max_concurrency,
    )

    created = await manager.create_job(job_req)
    await manager.start_job(created.job_id)

    return responses.RedirectResponse(
        url=f"/jobs/{created.job_id}/monitor",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/jobs/{job_id}/monitor")
async def job_monitor_view(
    job_id: str,
    request: Request,
    manager: JobManager = Depends(get_job_manager),
):
    """Live monitor dashboard matching Section 7.4 wireframe."""
    job = await manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return templates.TemplateResponse(
        request=request,
        name="job_monitor.html",
        context={"job": job.model_dump(), "active_tab": "dashboard"},
    )


@router.get("/jobs/{job_id}/results-view")
async def job_results_view(
    job_id: str,
    request: Request,
    manager: JobManager = Depends(get_job_manager),
):
    """Document results viewer."""
    job = await manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    pages = await manager.storage.get_pages_by_job(job_id)

    return templates.TemplateResponse(
        request=request,
        name="results.html",
        context={"job": job.model_dump(), "pages": pages, "active_tab": "dashboard"},
    )


@router.get("/jobs/{job_id}/errors-view")
async def job_errors_view(
    job_id: str,
    request: Request,
    manager: JobManager = Depends(get_job_manager),
):
    """Categorized error inspector."""
    job = await manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    errors = await manager.storage.get_errors_by_job(job_id)

    return templates.TemplateResponse(
        request=request,
        name="errors.html",
        context={"job": job.model_dump(), "errors": errors, "active_tab": "dashboard"},
    )
