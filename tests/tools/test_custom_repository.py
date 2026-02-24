# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for CustomToolRepository."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.models.base import Base
from flydesk.tools.custom_models import CustomTool, ToolSource
from flydesk.tools.custom_repository import CustomToolRepository


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def repo(session_factory):
    return CustomToolRepository(session_factory)


def _sample_tool(**overrides) -> CustomTool:
    defaults = dict(
        id="tool-001",
        name="calculate_risk",
        description="Calculate credit risk",
        python_code='import json, sys\nprint(json.dumps({"score": 85}))',
        parameters={"order_id": {"type": "string", "required": True}},
    )
    defaults.update(overrides)
    return CustomTool(**defaults)


class TestCustomToolRepository:
    async def test_create_and_get(self, repo):
        tool = _sample_tool()
        created = await repo.create(tool)
        assert created.id == "tool-001"
        assert created.name == "calculate_risk"

        fetched = await repo.get("tool-001")
        assert fetched is not None
        assert fetched.name == "calculate_risk"

    async def test_get_by_name(self, repo):
        await repo.create(_sample_tool())
        fetched = await repo.get_by_name("calculate_risk")
        assert fetched is not None
        assert fetched.id == "tool-001"

    async def test_get_by_name_not_found(self, repo):
        result = await repo.get_by_name("nonexistent")
        assert result is None

    async def test_list_all(self, repo):
        await repo.create(_sample_tool(id="t1", name="tool_a"))
        await repo.create(_sample_tool(id="t2", name="tool_b"))
        tools = await repo.list()
        assert len(tools) == 2

    async def test_list_by_source(self, repo):
        await repo.create(_sample_tool(id="t1", name="manual_tool", source=ToolSource.MANUAL))
        await repo.create(_sample_tool(id="t2", name="builtin_tool", source=ToolSource.BUILTIN))
        manual = await repo.list(source=ToolSource.MANUAL)
        assert len(manual) == 1
        assert manual[0].name == "manual_tool"

    async def test_list_active_only(self, repo):
        await repo.create(_sample_tool(id="t1", name="active_tool", active=True))
        await repo.create(_sample_tool(id="t2", name="inactive_tool", active=False))
        active = await repo.list(active_only=True)
        assert len(active) == 1
        assert active[0].name == "active_tool"

    async def test_list_with_pagination(self, repo):
        for i in range(5):
            await repo.create(_sample_tool(id=f"t{i}", name=f"tool_{i:02d}"))
        page = await repo.list(limit=2, offset=2)
        assert len(page) == 2

    async def test_update(self, repo):
        await repo.create(_sample_tool())
        tool = await repo.get("tool-001")
        updated = tool.model_copy(update={"description": "Updated description"})
        result = await repo.update(updated)
        assert result.description == "Updated description"

    async def test_update_nonexistent(self, repo):
        tool = _sample_tool(id="nope")
        with pytest.raises(ValueError, match="not found"):
            await repo.update(tool)

    async def test_delete(self, repo):
        await repo.create(_sample_tool())
        deleted = await repo.delete("tool-001")
        assert deleted is True
        assert await repo.get("tool-001") is None

    async def test_delete_nonexistent(self, repo):
        deleted = await repo.delete("nope")
        assert deleted is False

    async def test_get_nonexistent(self, repo):
        assert await repo.get("nope") is None

    async def test_parameters_roundtrip(self, repo):
        """Verify JSON parameters survive the SQLite text roundtrip."""
        params = {"order_id": {"type": "string", "required": True}}
        await repo.create(_sample_tool(parameters=params))
        fetched = await repo.get("tool-001")
        assert fetched.parameters == params

    async def test_timestamps_populated(self, repo):
        """Verify created_at and updated_at are set automatically."""
        created = await repo.create(_sample_tool())
        assert created.created_at is not None
        assert created.updated_at is not None
