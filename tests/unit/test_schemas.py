"""Unit tests for Pydantic schemas."""
import pytest
from datetime import date
from pydantic import ValidationError
from src.schemas.requests import ResearchRequest
from src.schemas.responses import (
    SourceMetadata,
    ArxivSource,
    ResearchStatus,
    ReportResponse,
    HealthResponse,
    ResearchResponse,
)


# ── ResearchRequest ────────────────────────────────────────────────────────────

def test_research_request_valid():
    req = ResearchRequest(query="Impact of LLMs on software engineering")
    assert req.query == "Impact of LLMs on software engineering"
    assert req.depth == "standard"
    assert req.sources_limit == 20


def test_research_request_query_too_short():
    with pytest.raises(ValidationError):
        ResearchRequest(query="AI")


def test_research_request_depth_options():
    for depth in ("quick", "standard", "deep"):
        req = ResearchRequest(query="Valid query here", depth=depth)
        assert req.depth == depth


def test_research_request_invalid_depth():
    with pytest.raises(ValidationError):
        ResearchRequest(query="Valid query here", depth="ultra")


# ── SourceMetadata ─────────────────────────────────────────────────────────────

def test_source_metadata_defaults():
    src = SourceMetadata(title="Test Paper")
    assert src.source_type == "web"
    assert src.relevance_score == 0.5
    assert src.url is None


def test_arxiv_source_fields():
    src = ArxivSource(
        title="Attention Is All You Need",
        authors=["Ashish Vaswani", "Noam Shazeer"],
        abstract="We propose a new simple network architecture...",
        arxiv_id="1706.03762",
        published_date=date(2017, 6, 12),
        relevance_score=0.95,
    )
    assert src.source_type == "web"
    assert len(src.authors) == 2
    assert src.arxiv_id == "1706.03762"


# ── ResearchStatus ─────────────────────────────────────────────────────────────

def test_research_status_instantiation():
    """Directly instantiate ResearchStatus to ensure all fields are covered."""
    status = ResearchStatus(
        job_id="abc123",
        status="queued",
        progress_pct=0,
        current_step="Initializing",
    )
    assert status.job_id == "abc123"
    assert status.status == "queued"
    assert status.trace_url is None
    assert status.error is None


def test_research_status_valid_statuses():
    for s in ("queued", "planning", "researching", "writing", "reviewing", "done", "failed"):
        status = ResearchStatus(
            job_id="test-job",
            status=s,
            progress_pct=50,
            current_step="Working",
        )
        assert status.status == s


def test_research_status_invalid_status():
    with pytest.raises(ValidationError):
        ResearchStatus(
            job_id="test-job",
            status="unknown",
            progress_pct=50,
            current_step="Working",
        )


# ── ResearchResponse ──────────────────────────────────────────────────────────

def test_research_response():
    resp = ResearchResponse(
        job_id="job-456",
        status="researching",
        stream_url="https://example.com/stream",
        estimated_duration="5m",
    )
    assert resp.job_id == "job-456"
    assert resp.status == "researching"


def test_research_response_invalid_status():
    with pytest.raises(ValidationError):
        ResearchResponse(
            job_id="job-456",
            status="unknown",
            stream_url="https://example.com/stream",
            estimated_duration="5m",
        )


# ── ReportResponse ─────────────────────────────────────────────────────────────

def test_report_response():
    from datetime import datetime
    resp = ReportResponse(
        job_id="job-789",
        report_markdown="# Report\n\nFindings here.",
        generated_at=datetime.utcnow(),
    )
    assert resp.job_id == "job-789"
    assert "Report" in resp.report_markdown
    assert resp.langgraph_version == "0.2.0"


def test_report_response_with_sources():
    from datetime import datetime
    src = SourceMetadata(title="Test Source", url="https://example.com")
    resp = ReportResponse(
        job_id="job-789",
        report_markdown="# Report",
        sources=[src],
        generated_at=datetime.utcnow(),
    )
    assert len(resp.sources) == 1


# ── HealthResponse ─────────────────────────────────────────────────────────────

def test_health_response():
    resp = HealthResponse(
        status="healthy",
        groq="up",
        tavily="up",
        arxiv="up",
        db="up",
    )
    assert resp.status == "healthy"
    assert resp.active_jobs == 0


def test_health_response_degraded():
    resp = HealthResponse(
        status="degraded",
        groq="down",
        tavily="up",
        arxiv="up",
        db="up",
        active_jobs=10,
    )
    assert resp.status == "degraded"
    assert resp.groq == "down"
    assert resp.active_jobs == 10
