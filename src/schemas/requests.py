"""Pydantic request schemas."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field

class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=5, max_length=1000, description="Research topic or question")
    depth: Literal["quick", "standard", "deep"] = "standard"
    max_iterations: int = Field(default=8, ge=1, le=20, description="Maximum agent iterations")
    sources_limit: int = Field(default=20, ge=5, le=100)
    include_academic: bool = Field(default=True)
    include_web: bool = Field(default=True)
    output_format: str = Field(default="both", pattern="^(markdown|pdf|both)$")
    language: str = Field(default="en", pattern="^(en|id)$")
    model_config = {"json_schema_extra": {"examples": [{"query": "Impact of LLMs on software engineering", "max_iterations": 8, "depth": "standard", "sources_limit": 20, "include_academic": True, "include_web": True}]}}
