"""Unit tests for research tools."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.agents.tools import _sanitize_html, tavily_search, arxiv_search, web_fetch

def test_sanitize_html():
    raw = "<script>alert('x')</script><p>Hello <b>World</b></p>"
    result = _sanitize_html(raw)
    assert "alert" not in result
    assert "Hello" in result
    assert "World" in result
    assert "<" not in result

def test_sanitize_html_truncation():
    long_text = "<p>" + "x" * 20_000 + "</p>"
    result = _sanitize_html(long_text)
    assert len(result) <= 10_000

@pytest.mark.asyncio
async def test_tavily_search_no_api_key():
    with patch("src.agents.tools.settings") as mock_settings:
        mock_settings.tavily_api_key = ""
        result = await tavily_search("test query")
        assert result == []

@pytest.mark.asyncio
async def test_tavily_search_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {"title": "Test Paper", "url": "https://example.com", "content": "Test snippet"}
        ]
    }
    with patch("src.agents.tools.settings") as mock_settings:
        mock_settings.tavily_api_key = "test-key"
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value.post.return_value = mock_response
            mock_client.return_value = mock_instance
            result = await tavily_search("test query")
            assert len(result) == 1
            assert result[0]["title"] == "Test Paper"
            assert result[0]["source_type"] == "web"

@pytest.mark.asyncio
async def test_web_fetch_html():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "text/html"}
    mock_response.text = "<html><body><p>Hello World</p></body></html>"
    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value.get.return_value = mock_response
        mock_client.return_value = mock_instance
        result = await web_fetch("https://example.com")
        assert "<" not in result
        assert "Hello" in result
        assert "World" in result

@pytest.mark.asyncio
async def test_web_fetch_non_html():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/pdf"}
    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value.get.return_value = mock_response
        mock_client.return_value = mock_instance
        result = await web_fetch("https://example.com/file.pdf")
        assert result == ""

@pytest.mark.asyncio
async def test_tavily_search_rate_limit():
    mock_response = MagicMock()
    mock_response.status_code = 429
    with patch("src.agents.tools.settings") as mock_settings:
        mock_settings.tavily_api_key = "test-key"
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value.post.return_value = mock_response
            mock_client.return_value = mock_instance
            from src.exceptions.handlers import TavilyRateLimitError
            with pytest.raises(TavilyRateLimitError):
                await tavily_search("test")

@pytest.mark.asyncio
async def test_arxiv_search_parses_atom():
    atom_xml = """<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <title>Test Paper Title</title>
        <summary>This is the abstract.</summary>
        <author><name>John Doe</name></author>
        <author><name>Jane Smith</name></author>
        <id>http://arxiv.org/abs/2401.00001v1</id>
        <published>2024-01-01T00:00:00Z</published>
      </entry>
    </feed>"""
    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = atom_xml
        mock_instance.__aenter__.return_value.get.return_value = mock_response
        mock_client.return_value = mock_instance
        results = await arxiv_search("test")
        assert len(results) == 1
        assert results[0]["title"] == "Test Paper Title"
        assert results[0]["authors"] == ["John Doe", "Jane Smith"]
        assert results[0]["source_type"] == "arxiv"
