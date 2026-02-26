# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for improved word-level memory search."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from flydesk.memory.models import CreateMemory
from flydesk.memory.repository import MemoryRepository
from flydesk.models import Base


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def repo(session_factory) -> MemoryRepository:
    return MemoryRepository(session_factory)


@pytest.fixture
def user_id():
    return f"user-{uuid.uuid4()}"


async def test_search_matches_individual_words(repo, user_id):
    """Search should match individual words, not require full substring."""
    await repo.create(user_id, CreateMemory(content="User prefers dark mode for the UI"))
    await repo.create(user_id, CreateMemory(content="User works in the finance department"))

    results = await repo.search(user_id, "What about dark theme settings?")
    assert len(results) >= 1
    assert any("dark" in m.content.lower() for m in results)


async def test_search_ignores_short_words(repo, user_id):
    """Words shorter than 3 chars should be ignored."""
    await repo.create(user_id, CreateMemory(content="User likes Python"))

    results = await repo.search(user_id, "is a python")
    assert len(results) >= 1
    assert any("Python" in m.content for m in results)


async def test_search_empty_after_filtering(repo, user_id):
    """If all words are too short, return empty."""
    await repo.create(user_id, CreateMemory(content="User likes Python"))
    results = await repo.search(user_id, "is it ok")
    assert results == []


async def test_search_limits_to_five_keywords(repo, user_id):
    """Only the first 5 meaningful words should be used."""
    await repo.create(user_id, CreateMemory(content="alpha beta gamma delta epsilon zeta"))
    results = await repo.search(user_id, "alpha beta gamma delta epsilon zeta eta")
    assert len(results) >= 1
