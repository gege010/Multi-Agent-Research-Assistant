"""Health check endpoints."""
from __future__ import annotations
import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from src.api.deps import get_db
from src.schemas.responses import HealthResponse
from src.config import get_settings
from src.db.models import ResearchJob

router = APIRouter(tags=["health"])

async def _check_groq() -> bool:
    settings = get_settings()
    if not settings.groq_api_key:
        return False
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.groq.com/v1/models",
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                timeout=5.0,
            )
            return resp.status_code in (200, 401)
    except Exception:
        return False

async def _check_tavily() -> bool:
    settings = get_settings()
    if not settings.tavily_api_key:
        return False
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.tavily.com/search",
                params={"api_key": settings.tavily_api_key, "query": "test"},
                timeout=5.0,
            )
            return resp.status_code in (200, 401, 403)
    except Exception:
        return False

async def _check_arxiv() -> bool:
    """Check if ArXiv is reachable (public endpoint)."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "http://export.arxiv.org/api/query?search_query=all:test&max_results=1",
                timeout=5.0,
            )
            return resp.status_code == 200
    except Exception:
        return False

@router.get("/health", response_model=HealthResponse, summary="Health check")
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    groq_up = await _check_groq()
    tavily_up = await _check_tavily()
    arxiv_up = await _check_arxiv()
    db_up = True
    try:
        result = await db.execute(
            select(func.count(ResearchJob.id)).where(
                ResearchJob.status.in_(["planning", "researching", "writing", "reviewing"])
            )
        )
        active_jobs = result.scalar() or 0
    except Exception:
        active_jobs = 0
        db_up = False
    if groq_up and tavily_up and db_up:
        overall = "healthy"
    elif db_up:
        overall = "degraded"
    else:
        overall = "unhealthy"
    return HealthResponse(
        status=overall,
        groq="up" if groq_up else "down",
        tavily="up" if tavily_up else "down",
        arxiv="up" if arxiv_up else "down",
        db="up" if db_up else "down",
        active_jobs=active_jobs,
    )

@router.get("/models", summary="Available LLM models")
async def list_models() -> dict:
    return {
        "models": [
            {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B Versatile"},
            {"id": "mixtral-8x7b-32768", "name": "Mixtral 8x7B"},
        ],
        "default": "llama-3.3-70b-versatile",
    }
