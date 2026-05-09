"""Tool definitions for LangGraph agents."""
from __future__ import annotations
import asyncio
import re
from typing import Any
import httpx
import structlog
from src.config import get_settings
from src.exceptions.handlers import TavilyRateLimitError, ArxivAPIError, APIError

logger = structlog.get_logger()
settings = get_settings()


def _sanitize_html(raw: str) -> str:
    """Strip HTML tags and clean text for LLM consumption."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", raw, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:10_000]


async def tavily_search(query: str, max_results: int = 10) -> list[dict]:
    """
    Search the web using Tavily API.
    Args:
        query: Search query string.
        max_results: Maximum number of results (default 10, max 20).
    Returns:
        List of search results with title, url, snippet, source_type, relevance_score.
    Raises:
        TavilyRateLimitError: When rate limit is hit.
    """
    if not settings.tavily_api_key:
        logger.warning("tavily_api_key_not_configured")
        return []

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": settings.tavily_api_key,
                    "query": query,
                    "max_results": min(max_results, 20),
                    "include_answer": False,
                    "include_raw_content": False,
                },
                timeout=30.0,
            )
            if resp.status_code == 429:
                raise TavilyRateLimitError("Tavily rate limit exceeded", detail=query)
            if resp.status_code != 200:
                raise APIError(f"Tavily API error: {resp.status_code}", detail=query)
            data = resp.json()
            results = data.get("results", [])
            logger.info("tavily_search_done", query=query, results_count=len(results))
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", ""),
                    "source_type": "web",
                    "relevance_score": 0.5,
                }
                for r in results
            ]
    except TavilyRateLimitError:
        raise
    except httpx.TimeoutException as exc:
        logger.warning("tavily_search_failed", query=query, error=str(exc))
        return []


def _parse_arxiv_atom(xml_text: str) -> list[dict]:
    """Parse ArXiv Atom XML feed into dict list."""
    results = []
    entries = re.findall(r"<entry>(.*?)</entry>", xml_text, re.DOTALL)
    for entry in entries:
        title = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
        summary = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)
        authors = re.findall(r"<name>(.*?)</name>", entry)
        link = re.search(r"<id>(.*?)</id>", entry)
        published = re.search(r"<published>(.*?)</published>", entry)
        arxiv_id_match = re.search(r"arxiv.org/abs/([^\s]+)", entry)
        results.append({
            "title": (title.group(1).strip().replace("\n", " ") if title else "Unknown"),
            "snippet": (summary.group(1).strip().replace("\n", " ") if summary else "")[:500],
            "url": link.group(1).strip() if link else "",
            "arxiv_id": arxiv_id_match.group(1) if arxiv_id_match else "",
            "authors": [a.strip() for a in authors],
            "published_date": (published.group(1)[:10] if published else ""),
            "source_type": "arxiv",
            "relevance_score": 0.6,
        })
    return results


async def arxiv_search(query: str, max_results: int = 10) -> list[dict]:
    """
    Search ArXiv for academic papers.
    Args:
        query: Search query string.
        max_results: Maximum number of results (default 10, max 50).
    Returns:
        List of paper results with title, authors, abstract, arxiv_id.
    Raises:
        ArxivAPIError: When ArXiv API returns an error.
    """
    # ArXiv limits: 1 request per 3 seconds per IP. Rate-limit via simple sleep.
    await asyncio.sleep(3.1)
    try:
        async with httpx.AsyncClient() as client:
            search_url = (
                f"https://export.arxiv.org/api/query"
                f"?search_query=all:{query}"
                f"&start=0"
                f"&max_results={min(max_results, 50)}"
                f"&sortBy=relevance"
            )
            resp = await client.get(search_url, timeout=30.0)
            if resp.status_code != 200:
                raise ArxivAPIError(f"ArXiv API error: {resp.status_code}")
            results = _parse_arxiv_atom(resp.text)
            logger.info("arxiv_search_done", query=query, results_count=len(results))
            return results
    except ArxivAPIError:
        raise
    except httpx.TimeoutException as exc:
        logger.warning("arxiv_search_failed", query=query, error=str(exc))
        return []


async def web_fetch(url: str) -> str:
    """
    Fetch and extract clean text from a URL.
    Args:
        url: Target URL to fetch.
    Returns:
        Cleaned text content (max 10,000 characters).
    """
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(url, timeout=30.0)
            if resp.status_code in (403, 404):
                logger.warning("web_fetch_failed", url=url, status=resp.status_code)
                return ""
            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                return ""
            raw = resp.text
            cleaned = _sanitize_html(raw)
            logger.info("web_fetch_done", url=url, chars=len(cleaned))
            return cleaned
    except httpx.TimeoutException as exc:
        logger.warning("web_fetch_failed", url=url, error=str(exc))
        return ""


async def read_document(url_or_path: str) -> str:
    """Read a document (URL or local PDF) using Unstructured.io."""
    try:
        from unstructured.partition.auto import partition
        import io
        
        # If it's a URL, download it first
        if url_or_path.startswith("http"):
            async with httpx.AsyncClient(follow_redirects=True) as client:
                resp = await client.get(url_or_path, timeout=30.0)
                if resp.status_code != 200:
                    return ""
                file_content = io.BytesIO(resp.content)
                elements = partition(file=file_content)
        else:
            elements = partition(filename=url_or_path)
            
        text = "\n\n".join([str(el) for el in elements])
        return text[:10000] # Limit size for LLM context
    except ImportError:
        logger.warning("unstructured_not_installed")
        return "Error: unstructured library is not installed."
    except Exception as exc:
        logger.warning("read_document_failed", path=url_or_path, error=str(exc))
        return f"Error reading document: {str(exc)}"


def execute_code(code: str) -> str:
    """Execute Python code in a REPL and return the output."""
    try:
        from langchain_experimental.utilities import PythonREPL
        repl = PythonREPL()
        result = repl.run(code)
        return result if result else "Code executed successfully with no output."
    except ImportError:
        logger.warning("langchain_experimental_not_installed")
        return "Error: langchain-experimental is not installed."
    except Exception as exc:
        logger.warning("execute_code_failed", error=str(exc))
        return f"Execution Error: {str(exc)}"
