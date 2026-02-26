# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for workspace is_system flag."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.models.base import Base
from flydesk.models.workspace import WorkspaceRow


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


class TestWorkspaceIsSystem:
    async def test_default_is_system_is_false(self, session_factory):
        async with session_factory() as session:
            row = WorkspaceRow(id="ws-1", name="Test")
            session.add(row)
            await session.commit()
            await session.refresh(row)
            assert row.is_system is False

    async def test_system_workspace_flag(self, session_factory):
        async with session_factory() as session:
            row = WorkspaceRow(id="ws-sys", name="System", is_system=True)
            session.add(row)
            await session.commit()
            await session.refresh(row)
            assert row.is_system is True
