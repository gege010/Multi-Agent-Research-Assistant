"""Research orchestration service."""
from __future__ import annotations
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from src.agents.state import default_state
from src.agents.supervisor import get_supervisor_graph
from src.repositories.job_repository import JobRepository
from src.services.report_service import ReportService
from src.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class ResearchService:
    def __init__(self, db: AsyncSession):
        self._db = db
        self._repo = JobRepository(db)
        self._report_service = ReportService()

    async def create_job(self, **kwargs) -> None:
        await self._repo.create(**kwargs)

    async def get_job(self, job_id: str):
        return await self._repo.get(job_id)

    async def cancel_job(self, job_id: str) -> None:
        await self._repo.update_status(job_id, "failed")
        await self._repo.update_error(job_id, "Cancelled by user")

    async def run_research(self, job_id: str, max_iterations: int = 8) -> None:
        """Execute the full research pipeline."""
        job = await self._repo.get(job_id)
        if not job:
            logger.error("job_not_found", job_id=job_id)
            return

        logger.info("research_started", job_id=job_id, query=job.query)
        try:
            await self._repo.update_status(job_id, "planning")
            state = default_state(
                query=job.query,
                job_id=job_id,
                depth="standard",
                language="en",
                include_academic=True,
                include_web=True,
                max_iterations=max_iterations,
            )
            graph = get_supervisor_graph()
            if settings.langsmith_tracing and settings.langsmith_api_key:
                try:
                    from langsmith.run_helpers import trace
                    with trace("research-assistant", project_name=settings.langsmith_project):
                        final_state = await graph.ainvoke(state)
                except Exception:
                    final_state = await graph.ainvoke(state)
            else:
                final_state = await graph.ainvoke(state)

            draft = final_state.get("draft", "")
            raw_sources = final_state.get("sources", [])
            # Extract plain dicts from whatever the sources list contains
            sources_json = []
            for s in raw_sources:
                if isinstance(s, dict):
                    sources_json.append({
                        "title": s.get("title", ""),
                        "url": s.get("url", ""),
                        "source_type": s.get("source_type", "web"),
                    })
                elif hasattr(s, "get"):
                    sources_json.append({
                        "title": s.get("title", ""),
                        "url": s.get("url", ""),
                        "source_type": s.get("source_type", "web"),
                    })
            trace_url = final_state.get("trace_url")
            await self._repo.update_result(
                job_id=job_id,
                report_markdown=draft,
                sources_json=sources_json,
                trace_url=trace_url,
            )
            logger.info("research_completed", job_id=job_id, draft_chars=len(draft))
        except Exception as exc:
            logger.error("research_failed", job_id=job_id, error=str(exc))
            await self._repo.update_error(job_id, str(exc))
