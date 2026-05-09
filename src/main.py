"""FastAPI application entry point."""
from __future__ import annotations
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.router import api_router
from src.config import get_settings
from src.db.database import init_db
from src.exceptions.handlers import register_exception_handlers

settings = get_settings()
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(
    title="Multi-Agent Research Assistant",
    description="Hierarchical LangGraph agent for autonomous research with LangSmith tracing",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
register_exception_handlers(app)
app.include_router(api_router)

@app.get("/", tags=["root"])
async def root() -> dict:
    return {"name": "Multi-Agent Research Assistant", "version": "0.1.0", "docs": "/docs"}
