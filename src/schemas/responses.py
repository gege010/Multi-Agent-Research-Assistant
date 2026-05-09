"""Pydantic response schemas."""
from __future__ import annotations
from datetime import datetime, date
from typing import Literal
from pydantic import BaseModel, Field

class SourceMetadata(BaseModel):
    title: str
    url: str | None = None
    doi: str | None = None
    source_type: Literal["web", "arxiv", "pdf", "other"] = "web"
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    relevance_score: float = Field(ge=0.0, le=1.0, default=0.5)

class ArxivSource(SourceMetadata):
    authors: list[str]
    abstract: str
    arxiv_id: str
    published_date: date

class ResearchResponse(BaseModel):
    job_id: str
    status: Literal["queued", "planning", "researching", "writing", "reviewing", "done", "failed"]
    stream_url: str
    estimated_duration: str

class ResearchStatus(BaseModel):
    job_id: str
    status: Literal["queued", "planning", "researching", "writing", "reviewing", "done", "failed"]
    progress_pct: int = Field(ge=0, le=100)
    current_step: str
    trace_url: str | None = None
    error: str | None = None

class ReportResponse(BaseModel):
    job_id: str
    report_markdown: str
    pdf_base64: str | None = None
    sources: list[SourceMetadata] = Field(default_factory=list)
    trace_url: str | None = None
    generated_at: datetime
    tokens_used: int | None = None
    langgraph_version: str = "0.2.0"
    report_content: str | None = None  # alias for report_markdown (API compat)

class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    groq: Literal["up", "down"]
    tavily: Literal["up", "down"]
    arxiv: Literal["up", "down"]
    db: Literal["up", "down"]
    active_jobs: int = 0
