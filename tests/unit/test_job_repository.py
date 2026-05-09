"""Unit tests for JobRepository."""
import pytest
from unittest.mock import AsyncMock
from src.repositories.job_repository import JobRepository
from src.db.models import ResearchJob

@pytest.fixture
def mock_db():
    return AsyncMock()

@pytest.mark.asyncio
async def test_create_job(mock_db):
    repo = JobRepository(mock_db)
    job = await repo.create(job_id="test-123", query="Test query", depth="quick", sources_limit=10)
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once()

@pytest.mark.asyncio
async def test_update_status(mock_db):
    repo = JobRepository(mock_db)
    await repo.update_status("test-123", "researching")
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()

@pytest.mark.asyncio
async def test_update_error(mock_db):
    repo = JobRepository(mock_db)
    await repo.update_error("test-123", "API timeout")
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()
