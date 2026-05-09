"""Job repository for database operations."""
from __future__ import annotations
from datetime import datetime
from typing import Sequence
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import ResearchJob

class JobRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(
        self,
        job_id: str,
        query: str,
        depth: str = "standard",
        sources_limit: int = 20,
        include_academic: bool = True,
        include_web: bool = True,
        output_format: str = "both",
        language: str = "en",
    ) -> ResearchJob:
        job = ResearchJob(id=job_id, query=query, status="queued")
        self._db.add(job)
        await self._db.commit()
        await self._db.refresh(job)
        return job

    async def get(self, job_id: str) -> ResearchJob | None:
        result = await self._db.execute(select(ResearchJob).where(ResearchJob.id == job_id))
        return result.scalar_one_or_none()

    async def update_status(self, job_id: str, status: str) -> None:
        await self._db.execute(update(ResearchJob).where(ResearchJob.id == job_id).values(status=status))
        await self._db.commit()

    async def update_result(self, job_id: str, report_markdown: str, sources_json: list[dict], trace_url: str | None = None) -> None:
        await self._db.execute(
            update(ResearchJob)
            .where(ResearchJob.id == job_id)
            .values(
                status="done",
                report_markdown=report_markdown,
                sources_json=sources_json,
                trace_url=trace_url,
                completed_at=datetime.utcnow(),
            )
        )
        await self._db.commit()

    async def update_error(self, job_id: str, error_message: str) -> None:
        await self._db.execute(
            update(ResearchJob).where(ResearchJob.id == job_id).values(status="failed", error=error_message)
        )
        await self._db.commit()

    async def update_trace_url(self, job_id: str, trace_url: str) -> None:
        await self._db.execute(
            update(ResearchJob).where(ResearchJob.id == job_id).values(trace_url=trace_url)
        )
        await self._db.commit()

    async def list_active(self) -> Sequence[ResearchJob]:
        result = await self._db.execute(
            select(ResearchJob).where(ResearchJob.status.in_(["planning", "researching", "writing", "reviewing"]))
        )
        return result.scalars().all()

    async def list_recent(self, limit: int = 20) -> Sequence[ResearchJob]:
        result = await self._db.execute(
            select(ResearchJob).order_by(ResearchJob.created_at.desc()).limit(limit)
        )
        return result.scalars().all()
