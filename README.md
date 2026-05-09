# Multi-Agent Research Assistant

> Hierarchical LangGraph agent for autonomous research with LangSmith tracing. Supports Tavily web search, ArXiv academic search, and PDF report generation.

## Features

- **Hierarchical Supervisor Agent** — LangGraph-powered multi-agent orchestration
  - Planner → Researcher → Writer → Reviewer
  - Self-correcting loop (up to 3 revisions)
- **Multi-source search** — Tavily (web) + ArXiv (academic papers)
- **PDF generation** — WeasyPrint HTML-to-PDF
- **Full observability** — LangSmith traces every tool call
- **Production-grade API** — FastAPI with SSE streaming
- **Docker-ready** — Single container, `docker compose up`

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your API keys

# 2. Start services
docker compose up --build

# 3. Open in browser
#   API:  http://localhost:8000/docs
#   UI:   http://localhost:8501
```

## Manual Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set API keys
export GROQ_API_KEY=gsr_xxxxx
export TAVILY_API_KEY=tvly_xxxxx
export LANGSMITH_API_KEY=lsv2_xxxxx

# Run API
uvicorn src.main:app --reload --port 8000

# Run UI (separate terminal)
streamlit run frontend/app.py --port 8501
```

## API Example

```bash
# Start research
curl -X POST http://localhost:8000/api/v1/research \
  -H "Content-Type: application/json" \
  -d '{"query": "Impact of LLMs on software engineering", "depth": "standard"}'

# Check status
curl http://localhost:8000/api/v1/research/{job_id}

# Get report
curl http://localhost:8000/api/v1/research/{job_id}/report
```

## Architecture

```
Streamlit UI ──► FastAPI ──► LangGraph Supervisor
                               │
                    ┌──────────┼──────────┐
                    ▼          ▼          ▼
               Planner   Researcher   Writer
                           │                     │
                    ┌──────┴──────┐         Reviewer
                    ▼             ▼             ▲
               Tavily        ArXiv              │
                    └─────────────┘        (loop back if needed)
                              │
                         LangSmith
                    (every tool call traced)
```

## Project Structure

```
src/
├── main.py                    # FastAPI entry point
├── config.py                  # Environment settings
├── api/
│   ├── router.py              # Route aggregation
│   ├── deps.py                 # Dependencies
│   └── v1/
│       ├── health.py           # /health, /models
│       └── research.py         # /research endpoints
├── agents/
│   ├── state.py               # AgentState TypedDict
│   ├── planner.py             # Break query into tasks
│   ├── researcher.py           # Execute searches
│   ├── writer.py              # Generate markdown
│   ├── reviewer.py            # Quality check
│   ├── supervisor.py          # LangGraph graph
│   └── tools.py               # tavily, arxiv, web_fetch
├── services/
│   ├── research_service.py    # Orchestration
│   └── report_service.py      # Markdown → PDF
├── repositories/
│   └── job_repository.py      # Job CRUD
├── schemas/                   # Pydantic schemas
├── db/                        # SQLAlchemy models
└── exceptions/                # Custom exception hierarchy
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent | LangGraph (hierarchical supervisor) |
| LLM | Groq (Llama-3.3 70B) |
| Search | Tavily + ArXiv |
| Observability | LangSmith |
| Web | FastAPI + Uvicorn |
| UI | Streamlit |
| PDF | WeasyPrint |
| DB | SQLite (SQLAlchemy) |
| Container | Docker |

## Environment Variables

See `.env.example` for all variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | ✅ | — | Groq API key |
| `LLM_MODEL` | ❌ | `llama-3.3-70b-versatile` | Groq model |
| `TAVILY_API_KEY` | ✅ | — | Tavily Search API key |
| `LANGSMITH_API_KEY` | ❌ | — | LangSmith API key (for tracing) |
| `LANGSMITH_PROJECT` | ❌ | `research-assistant` | LangSmith project name |
| `APP_ENV` | ❌ | `development` | `development` or `production` |
| `DATABASE_URL` | ❌ | SQLite | Database connection string |

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```
