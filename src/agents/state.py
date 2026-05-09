"""LangGraph agent state definitions."""
from __future__ import annotations
import operator
from typing import Annotated, Literal, TypedDict


class AgentState(TypedDict):
    """Shared state across all agent nodes."""

    # Core inputs
    query: str
    depth: Literal["quick", "standard", "deep"]
    language: Literal["en", "id"]
    include_academic: bool
    include_web: bool
    max_iterations: int

    # Intermediate outputs
    plan: Annotated[list[str], operator.add]  # accumulated search tasks
    sources: list[dict]  # gathered sources — plain list (no add_messages, avoids LangChain message wrapping)
    draft: str  # markdown report draft
    review_score: float
    revision_count: int
    gap_analysis: str | None
    current_iteration: int
    next_node: str | None

    # Metadata
    status: Literal[
        "planning", "researching", "writing", "reviewing", "done", "failed"
    ]
    trace_url: str | None
    error: str | None
    job_id: str | None


def default_state(
    query: str,
    job_id: str,
    depth: str = "standard",
    language: str = "en",
    include_academic: bool = True,
    include_web: bool = True,
    max_iterations: int = 8,
) -> AgentState:
    """Factory for initial agent state."""
    return AgentState(
        query=query,
        depth=depth,  # type: ignore[arg-type]
        language=language,  # type: ignore[arg-type]
        include_academic=include_academic,
        include_web=include_web,
        max_iterations=max_iterations,
        plan=[],
        sources=[],
        draft="",
        review_score=0.0,
        revision_count=0,
        gap_analysis=None,
        current_iteration=0,
        next_node=None,
        status="planning",
        trace_url=None,
        error=None,
        job_id=job_id,
    )