"""FastAPI router aggregator."""
from __future__ import annotations
from fastapi import APIRouter
from src.api.v1 import research, health

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(research.router)
