# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for user memory repository."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from flydesk.memory.models import CreateMemory, UpdateMemory
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


class TestMemoryRepository:
    async def test_create_and_get(self, repo):
        mem = await repo.create("user-1", CreateMemory(content="I prefer dark mode"))
        assert mem.id
        assert mem.content == "I prefer dark mode"
        assert mem.category == "general"
        assert mem.source == "agent"

        fetched = await repo.get("user-1", mem.id)
        assert fetched is not None
        assert fetched.content == "I prefer dark mode"

    async def test_get_scoped_by_user(self, repo):
        mem = await repo.create("user-1", CreateMemory(content="secret"))
        result = await repo.get("user-2", mem.id)
        assert result is None

    async def test_list_for_user(self, repo):
        await repo.create("user-1", CreateMemory(content="mem 1"))
        await repo.create("user-1", CreateMemory(content="mem 2", category="preference"))
        await repo.create("user-2", CreateMemory(content="other user"))

        all_mems = await repo.list_for_user("user-1")
        assert len(all_mems) == 2

        prefs = await repo.list_for_user("user-1", category="preference")
        assert len(prefs) == 1
        assert prefs[0].content == "mem 2"

    async def test_update(self, repo):
        mem = await repo.create("user-1", CreateMemory(content="old"))
        updated = await repo.update("user-1", mem.id, UpdateMemory(content="new"))
        assert updated is not None
        assert updated.content == "new"

    async def test_update_wrong_user(self, repo):
        mem = await repo.create("user-1", CreateMemory(content="mine"))
        result = await repo.update("user-2", mem.id, UpdateMemory(content="stolen"))
        assert result is None

    async def test_delete(self, repo):
        mem = await repo.create("user-1", CreateMemory(content="tmp"))
        assert await repo.delete("user-1", mem.id) is True
        assert await repo.get("user-1", mem.id) is None

    async def test_delete_wrong_user(self, repo):
        mem = await repo.create("user-1", CreateMemory(content="mine"))
        assert await repo.delete("user-2", mem.id) is False

    async def test_search(self, repo):
        await repo.create("user-1", CreateMemory(content="I love dark mode"))
        await repo.create("user-1", CreateMemory(content="My timezone is UTC"))
        await repo.create("user-2", CreateMemory(content="I also love dark mode"))

        results = await repo.search("user-1", "dark")
        assert len(results) == 1
        assert "dark" in results[0].content
