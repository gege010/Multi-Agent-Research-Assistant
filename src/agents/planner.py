"""Planner agent node — breaks query into search tasks."""
from __future__ import annotations
import structlog
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from src.agents.state import AgentState
from src.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

class ResearchPlan(BaseModel):
    tasks: list[str] = Field(description="List of 3-5 focused search tasks")

PLANNER_SYSTEM = """You are a Research Planner. Given a research query, break it down into 3-5 focused search tasks that together will produce a comprehensive report.

Rules:
- Each task should target a different angle (background, methods, results, opinions, latest news)
- Tasks should be specific enough to yield useful results, not generic
- Include academic search for research queries, web search for current info
- Max 5 tasks total"""

async def planner_node(state: AgentState) -> dict:
    """Break the research query into actionable search tasks."""
    llm = ChatGroq(api_key=settings.groq_api_key, model=settings.llm_model, temperature=0.1)
    structured_llm = llm.with_structured_output(ResearchPlan)
    
    messages = [
        SystemMessage(content=PLANNER_SYSTEM),
        HumanMessage(content=f"Research query: {state['query']}\nDepth: {state['depth']}"),
    ]
    
    try:
        response = await structured_llm.ainvoke(messages)
        tasks = response.tasks
    except Exception as e:
        logger.error("planner_structured_output_failed", error=str(e))
        # Fallback if structured output fails
        tasks = [
            f"General overview: {state['query']}",
            f"Academic research: {state['query']}",
            f"Recent developments: {state['query']}",
        ]
        
    logger.info("planner_done", job_id=state["job_id"], tasks=len(tasks))
    return {"plan": tasks, "status": "researching"}
