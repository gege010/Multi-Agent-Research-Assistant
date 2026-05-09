"""LangGraph supervisor graph — orchestrates all agent nodes."""
from __future__ import annotations
import structlog
from langgraph.graph import StateGraph, END
from src.agents.state import AgentState
from src.agents.planner import planner_node
from src.agents.researcher import researcher_node
from src.agents.writer import writer_node
from src.agents.reviewer import reviewer_node

logger = structlog.get_logger()

def build_supervisor_graph():
    """Build and compile the LangGraph research supervisor."""
    graph = StateGraph(AgentState)
    graph.add_node("planner", planner_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("writer", writer_node)
    graph.add_node("reviewer", reviewer_node)
    graph.set_entry_point("planner")

    def router_decision(state: AgentState) -> str:
        """Decide whether to execute tools, reflect, or move to writer."""
        next_node = state.get("next_node")
        if next_node == "researcher":
            return "researcher"
        return "writer"

    def review_decision(state: AgentState) -> str:
        """Decide whether to loop back to research or finish."""
        status = state.get("status", "reviewing")
        if status == "done":
            return END
        return "researcher"

    graph.add_edge("planner", "researcher")
    graph.add_conditional_edges("researcher", router_decision, {"researcher": "researcher", "writer": "writer"})
    graph.add_edge("writer", "reviewer")
    graph.add_conditional_edges("reviewer", review_decision, {"researcher": "researcher", END: END})
    
    return graph.compile()

_supervisor_graph = None

def get_supervisor_graph():
    global _supervisor_graph
    if _supervisor_graph is None:
        _supervisor_graph = build_supervisor_graph()
    return _supervisor_graph
