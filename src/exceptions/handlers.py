"""Custom exception hierarchy and FastAPI handlers."""
from __future__ import annotations
from fastapi import Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
import structlog

logger = structlog.get_logger()

class ResearchAssistantError(Exception):
    def __init__(self, message: str, detail: str | None = None):
        self.message = message
        self.detail = detail
        super().__init__(message)

class APIError(ResearchAssistantError): pass
class TavilyRateLimitError(APIError): pass
class GroqAPIError(APIError): pass
class ArxivAPIError(APIError): pass
class AgentError(ResearchAssistantError): pass
class MaxRetriesExceededError(AgentError): pass
class LLMTimeoutError(AgentError): pass
class ValidationSchemaError(ResearchAssistantError): pass
class StorageError(ResearchAssistantError): pass

def register_exception_handlers(app) -> None:
    @app.exception_handler(ResearchAssistantError)
    async def research_assistant_error_handler(request: Request, exc: ResearchAssistantError):
        logger.error("application_error", message=exc.message, detail=exc.detail)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": exc.message, "detail": exc.detail},
        )
    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "Validation error", "detail": exc.errors()},
        )
    @app.exception_handler(TavilyRateLimitError)
    async def tavily_error_handler(request: Request, exc: TavilyRateLimitError):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"error": exc.message, "detail": exc.detail},
        )
    @app.exception_handler(GroqAPIError)
    async def groq_error_handler(request: Request, exc: GroqAPIError):
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"error": exc.message, "detail": exc.detail},
        )
    @app.exception_handler(ArxivAPIError)
    async def arxiv_error_handler(request: Request, exc: ArxivAPIError):
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"error": exc.message, "detail": exc.detail},
        )
    @app.exception_handler(ValidationSchemaError)
    async def validation_schema_error_handler(request: Request, exc: ValidationSchemaError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": exc.message, "detail": exc.detail},
        )
