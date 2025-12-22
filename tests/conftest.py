"""Pytest fixtures for tests."""

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from src.database import DatabaseManager, Repository


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[DatabaseManager, None]:
    """Create in-memory database for testing."""
    db = DatabaseManager("sqlite+aiosqlite:///:memory:")
    await db.init_db()
    yield db
    await db.close()


@pytest_asyncio.fixture
async def repo(db: DatabaseManager) -> AsyncGenerator[Repository, None]:
    """Create repository with test database session."""
    async with db.session() as session:
        yield Repository(session)
