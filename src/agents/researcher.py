"""Researcher agent node — executes searches and gathers sources."""
from __future__ import annotations
import json
import structlog
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from src.agents.state import AgentState
from src.agents.tools import tavily_search, arxiv_search, read_document, execute_code
from src.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

RESEARCHER_SYSTEM = """You are an autonomous Research Assistant. Your goal is to gather information to answer the user's query by executing the provided research plan.
You have access to several tools. Use them to gather data. 
If you have enough information to write a comprehensive report, or if you have tried multiple times without success, output the string "ENOUGH_INFO" (without quotes) as your response instead of calling a tool.

Current Plan:
{plan}

Gap Analysis from previous review (if any):
{gap_analysis}
"""

async def researcher_node(state: AgentState) -> dict:
    """Execute search tasks using LLM routing."""
    # Enforce max iterations
    current_iteration = state.get("current_iteration", 0)
    max_iterations = state.get("max_iterations", 8)
    
    if current_iteration >= max_iterations:
        logger.warning("max_iterations_reached", job_id=state["job_id"], iterations=current_iteration)
        return {"status": "writing", "next_node": "writer"}

    llm = ChatGroq(api_key=settings.groq_api_key, model=settings.llm_model, temperature=0.2)
    tools = [tavily_search, arxiv_search, read_document, execute_code]
    
    # Filter tools based on settings
    active_tools = []
    if state.get("include_web", True):
        active_tools.append(tavily_search)
    if state.get("include_academic", True):
        active_tools.append(arxiv_search)
    active_tools.extend([read_document, execute_code])
    
    llm_with_tools = llm.bind_tools(active_tools)

    # Reconstruct plan as a string for the prompt
    raw_plan = state.get("plan") or []
    plan_str = ""
    for idx, item in enumerate(raw_plan):
        content = item.content if hasattr(item, "content") else str(item)
        plan_str += f"{idx + 1}. {content}\n"

    system_msg = RESEARCHER_SYSTEM.format(
        plan=plan_str,
        gap_analysis=state.get("gap_analysis", "None")
    )
    
    messages = [SystemMessage(content=system_msg)]
    messages.append(HumanMessage(content=f"Query: {state['query']}"))

    # Add history of sources/tool calls to provide context
    sources = state.get("sources", [])
    if sources:
        sources_summary = "Sources gathered so far:\n"
        for s in sources[-5:]: # Only show last 5 to save context
            if isinstance(s, dict):
                sources_summary += f"- {s.get('title', 'Unknown')} ({s.get('source_type', 'tool')})\n"
        messages.append(HumanMessage(content=sources_summary))

    response = await llm_with_tools.ainvoke(messages)
    
    # Check if LLM decided it has enough info or if it called tools
    if "ENOUGH_INFO" in response.content or not response.tool_calls:
        logger.info("researcher_decision", job_id=state["job_id"], decision="write")
        return {"status": "writing", "next_node": "writer", "current_iteration": current_iteration + 1}
    
    # If tools were called, simulate the tool execution (LangGraph ToolNode handles the actual execution)
    # We just need to update the state with the tool calls
    logger.info("researcher_decision", job_id=state["job_id"], decision="tools", calls=len(response.tool_calls))
    
    # In a real LangGraph setup with ToolNode, we append the AIMessage with tool_calls
    # to a "messages" list. Since our state uses "sources" list for results, 
    # we need to adapt. The ToolNode expects a "messages" key.
    # To keep our existing state structure simple, we'll execute tools manually here
    # rather than relying on ToolNode to avoid changing the entire state architecture.
    
    new_sources = []
    for tool_call in response.tool_calls:
        name = tool_call["name"]
        args = tool_call["args"]
        
        try:
            if name == "tavily_search" and tavily_search in active_tools:
                res = await tavily_search(**args)
                new_sources.extend(res)
            elif name == "arxiv_search" and arxiv_search in active_tools:
                res = await arxiv_search(**args)
                new_sources.extend(res)
            elif name == "read_document":
                res = await read_document(**args)
                new_sources.append({"title": f"Doc: {args.get('url_or_path', '')}", "snippet": res, "source_type": "document"})
            elif name == "execute_code":
                res = execute_code(**args)
                new_sources.append({"title": "Code Execution Result", "snippet": res, "source_type": "code"})
        except Exception as e:
            logger.error("tool_execution_failed", tool=name, error=str(e))
            
    # Combine old and new sources
    all_sources = list(sources) + new_sources
    
    return {
        "sources": all_sources, 
        "status": "researching", 
        "next_node": "tools", # Forces loop back to researcher in our simplified graph
        "current_iteration": current_iteration + 1
    }
