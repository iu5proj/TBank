"""Shared test fixtures and configuration."""

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_db():
    """Mock database session for unit tests."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.close = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def sample_resume_data() -> dict:
    """Standard resume payload for tests."""
    return {
        "job_title": "Senior Python Developer",
        "experience_years": 5.0,
        "skills": ["Python", "FastAPI", "PostgreSQL"],
        "location": "Москва",
        "education_level": "bachelor",
        "experience_entries": [
            {
                "company": "Яндекс",
                "title": "Backend Developer",
                "duration_months": 24,
                "description": "Разрабатывал высоконагруженные сервисы",
            }
        ],
    }


@pytest.fixture
def sample_estimate_data() -> dict:
    """Standard estimate request payload."""
    return {
        "job_title": "Senior Python Developer",
        "experience_years": 5.0,
        "skills": ["Python", "FastAPI", "PostgreSQL"],
        "location": "Москва",
        "education_level": "bachelor",
        "experience_entries": [],
    }


@pytest.fixture
def client() -> TestClient:
    """Synchronous test client."""
    return TestClient(app)


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Async test client for async endpoint tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
