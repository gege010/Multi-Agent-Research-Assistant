"""Research job endpoints."""
from __future__ import annotations
import os
import uuid
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import get_db
from src.schemas.requests import ResearchRequest
from src.schemas.responses import ResearchResponse, ResearchStatus, ReportResponse
from src.db.models import ResearchJob
from src.services.research_service import ResearchService
from src.repositories.job_repository import JobRepository

router = APIRouter(prefix="/research", tags=["research"])

# Reports output directory
REPORTS_DIR = Path("data/reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

@router.post("", response_model=ResearchResponse, summary="Start research job")
async def start_research(
    request: ResearchRequest,
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> ResearchResponse:
    job_id = str(uuid.uuid4())
    service = ResearchService(db)
    await service.create_job(
        job_id=job_id,
        query=request.query,
        depth=request.depth,
        sources_limit=request.sources_limit,
        include_academic=request.include_academic,
        include_web=request.include_web,
        output_format=request.output_format,
        language=request.language,
    )
    background_tasks.add_task(service.run_research, job_id, request.max_iterations)
    return ResearchResponse(
        job_id=job_id,
        status="queued",
        stream_url=f"/api/v1/research/{job_id}/stream",
        estimated_duration="~2-5 minutes",
    )

@router.get("/{job_id}", response_model=ResearchStatus, summary="Get job status")
async def get_job_status(job_id: str, db: AsyncSession = Depends(get_db)) -> ResearchStatus:
    service = ResearchService(db)
    job = await service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    status_map = {
        "queued": (5, "Waiting in queue"),
        "planning": (20, "Planning search strategy"),
        "researching": (50, "Gathering sources"),
        "writing": (75, "Writing report"),
        "reviewing": (90, "Quality review"),
        "done": (100, "Completed"),
        "failed": (100, f"Failed: {job.error or 'Unknown error'}"),
    }
    progress, step = status_map.get(job.status, (0, "Unknown"))
    return ResearchStatus(
        job_id=job.id,
        status=job.status,
        progress_pct=progress,
        current_step=step,
        trace_url=job.trace_url,
        error=job.error,
    )

@router.get("/{job_id}/report", response_model=ReportResponse, summary="Get full report")
async def get_report(job_id: str, db: AsyncSession = Depends(get_db)) -> ReportResponse:
    service = ResearchService(db)
    job = await service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status != "done":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Report not ready yet")
    return ReportResponse(
        job_id=job.id,
        report_markdown=job.report_markdown or "",
        sources=[],
        trace_url=job.trace_url,
        generated_at=job.completed_at or datetime.utcnow(),
        langgraph_version="0.2.0",
    )


@router.get("/{job_id}/report/download", summary="Download report as Markdown file")
async def download_markdown(job_id: str, db: AsyncSession = Depends(get_db)) -> FileResponse:
    """Download the research report as a .md file."""
    service = ResearchService(db)
    job = await service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status != "done":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Report not ready yet")

    markdown = job.report_markdown or ""
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in job.query)[:50]
    filename = f"{job_id[:8]}_{safe_title}.md"
    filepath = REPORTS_DIR / filename
    filepath.write_text(markdown, encoding="utf-8")

    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type="text/markdown",
    )


@router.get("/{job_id}/report/pdf", summary="Download report as PDF file")
async def download_pdf(job_id: str, db: AsyncSession = Depends(get_db)) -> FileResponse:
    """Download the research report as a .pdf file."""
    service = ResearchService(db)
    job = await service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status != "done":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Report not ready yet")

    markdown = job.report_markdown or ""
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in job.query)[:50]
    filename = f"{job_id[:8]}_{safe_title}.pdf"
    filepath = REPORTS_DIR / filename

    try:
        from src.services.report_service import ReportService
        report_service = ReportService()
        filepath.write_bytes(report_service.markdown_to_pdf(markdown))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"PDF generation unavailable: {str(exc)}. Download the .md file instead.",
        )

    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type="application/pdf",
    )

@router.delete("/{job_id}", summary="Cancel job")
async def cancel_job(job_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    service = ResearchService(db)
    job = await service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.is_terminal:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job already finished")
    await service.cancel_job(job_id)
    return {"message": "Job cancelled"}


@router.get("", summary="List all jobs")
async def list_jobs(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return recent research jobs ordered by created_at desc."""
    repo = JobRepository(db)
    jobs = await repo.list_recent(limit=limit)
    return [
        {
            "job_id": j.id,
            "query": j.query,
            "status": j.status,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            "trace_url": j.trace_url,
            "error": j.error,
        }
        for j in reversed(jobs)
    ]
