# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for list_recent memory retrieval."""

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


@pytest.mark.asyncio
async def test_list_recent_returns_most_recent(repo, user_id):
    """list_recent returns the N most recently created memories."""
    for i in range(7):
        await repo.create(user_id, CreateMemory(content=f"Memory {i}"))
    recent = await repo.list_recent(user_id, limit=3)
    assert len(recent) == 3
    assert recent[0].content == "Memory 6"
    assert recent[1].content == "Memory 5"
    assert recent[2].content == "Memory 4"


@pytest.mark.asyncio
async def test_list_recent_defaults_to_five(repo, user_id):
    """Default limit is 5."""
    for i in range(10):
        await repo.create(user_id, CreateMemory(content=f"Memory {i}"))
    recent = await repo.list_recent(user_id)
    assert len(recent) == 5


@pytest.mark.asyncio
async def test_list_recent_empty_user(repo):
    """Returns empty list for user with no memories."""
    recent = await repo.list_recent("nonexistent-user")
    assert recent == []
