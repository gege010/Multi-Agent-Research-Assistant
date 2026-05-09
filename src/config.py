from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    llm_model: str = Field(default="llama-3.3-70b-versatile", alias="LLM_MODEL")
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")
    langsmith_api_key: str = Field(default="", alias="LANGSMITH_API_KEY")
    langsmith_tracing: bool = Field(default=True, alias="LANGSMITH_TRACING")
    langsmith_project: str = Field(default="research-assistant", alias="LANGSMITH_PROJECT")
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    max_concurrent_jobs: int = Field(default=3, alias="MAX_CONCURRENT_JOBS")
    revision_max: int = Field(default=2, alias="REVISION_MAX")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./research_assistant.db",
        alias="DATABASE_URL",
    )

    @property
    def is_production(self) -> bool:
        """Check if the application is running in production mode."""
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
