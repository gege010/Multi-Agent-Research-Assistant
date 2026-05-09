"""Writer agent node — generates structured markdown report."""
from __future__ import annotations
import structlog
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from src.agents.state import AgentState
from src.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

WRITER_SYSTEM_EN = """You are an expert research report writer. Given a research query and a set of gathered sources, write a comprehensive, well-structured markdown research report.

Report structure:
1. # Title (from query)
2. ## Executive Summary (2-3 sentences)
3. ## Introduction (context, scope, why this matters)
4. ## Literature Review (categorized findings from sources)
5. ## Key Findings (with in-text citations like [1])
6. ## Analysis & Discussion (your interpretation)
7. ## Conclusion (summary + future directions)
8. ## References (formatted citation list)

Rules:
- Write in formal academic style
- Include citations as [N] referencing the sources list
- For each key finding, cite 1-3 sources
- Language: English
- Output ONLY the markdown report, no commentary"""

WRITER_SYSTEM_ID = """Anda adalah penulis laporan riset profesional. Given research query and sources, write comprehensive Indonesian markdown report with: # Title, ## Ringkasan Eksekutif, ## Pendahuluan, ## Tinjauan Pustaka, ## Temuan Utama, ## Analisis & Pembahasan, ## Kesimpulan, ## Referensi."""


async def writer_node(state: AgentState) -> dict:
    """Generate the structured markdown report."""
    llm = ChatGroq(api_key=settings.groq_api_key, model=settings.llm_model, temperature=0.3)
    raw_sources = state.get("sources") or []
    # Unwrap LangChain message wrappers (add_messages reducer wraps dicts as AIMessage)
    sources = []
    for item in raw_sources:
        if isinstance(item, dict):
            sources.append(item)
        elif hasattr(item, "content"):
            try:
                sources.append(item.content)
            except Exception:
                pass
        elif hasattr(item, "dict"):
            try:
                sources.append(item.dict())
            except Exception:
                pass
    language = state.get("language", "en")
    system_prompt = WRITER_SYSTEM_EN if language == "en" else WRITER_SYSTEM_ID

    sources_text = ""
    for i, src in enumerate(sources[:30], 1):
        sources_text += f"[{i}] {src.get('title', 'Unknown')}\n"
        sources_text += f"    URL: {src.get('url', 'N/A')}\n"
        if src.get("snippet"):
            sources_text += f"    Snippet: {src.get('snippet', '')[:300]}\n"
        if src.get("authors"):
            sources_text += f"    Authors: {', '.join(src.get('authors', []))}\n"
        sources_text += "\n"

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Research Query: {state['query']}\n\nSources ({len(sources)} total):\n{sources_text}\n\nWrite the complete research report now."),
    ]
    response = await llm.ainvoke(messages)
    draft = response.content.strip()
    logger.info("writer_done", job_id=state["job_id"], draft_chars=len(draft))
    return {"draft": draft, "status": "reviewing"}
