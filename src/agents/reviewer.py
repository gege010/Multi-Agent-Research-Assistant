"""Reviewer agent node — validates report quality."""
from __future__ import annotations
import structlog
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from src.agents.state import AgentState
from src.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

REVIEWER_SYSTEM = """You are a research quality reviewer. Evaluate a research report on a scale of 0.0 to 1.0.

Score rubric:
- 0.9-1.0: Excellent — comprehensive, well-cited, clear structure
- 0.7-0.9: Good — solid report, minor gaps
- 0.5-0.7: Acceptable — needs revision, some missing sections
- 0.0-0.5: Poor — incomplete, uncited, poorly structured

Also provide:
1. A gap_analysis string describing what's missing or weak (empty string if score >= 0.8)
2. A brief decision: "approve" if score >= 0.8, "revise" if lower

Output format:
SCORE: 0.XX
DECISION: approve/revise
GAP_ANALYSIS: [description of gaps, or "none"]"""

async def reviewer_node(state: AgentState) -> dict:
    """Evaluate report quality and decide approval or revision."""
    llm = ChatGroq(api_key=settings.groq_api_key, model=settings.llm_model, temperature=0.0)
    messages = [
        SystemMessage(content=REVIEWER_SYSTEM),
        HumanMessage(content=f"Research Query: {state['query']}\n\nReport:\n{state.get('draft', '')}"),
    ]
    response = await llm.ainvoke(messages)
    raw_review = response.content.strip()

    score = 0.5
    decision = "approve"
    gap_analysis = ""
    for line in raw_review.split("\n"):
        line = line.strip()
        if line.startswith("SCORE:"):
            try:
                score = float(line.split(":")[1].strip())
            except ValueError:
                pass
        elif line.startswith("DECISION:"):
            decision = line.split(":")[1].strip().lower()
        elif line.startswith("GAP_ANALYSIS:"):
            gap_analysis = line.split(":", 1)[1].strip()

    revision_count = state.get("revision_count", 0) + 1
    logger.info("reviewer_done", job_id=state["job_id"], score=score, decision=decision, revision_count=revision_count)

    if decision == "approve" or score >= 0.8:
        return {"review_score": score, "gap_analysis": gap_analysis, "revision_count": revision_count, "status": "done"}

    if revision_count >= settings.revision_max:
        logger.warning("max_revisions_reached", job_id=state["job_id"])
        return {"review_score": score, "gap_analysis": gap_analysis, "revision_count": revision_count, "status": "done"}

    return {"review_score": score, "gap_analysis": gap_analysis, "revision_count": revision_count, "status": "researching"}
