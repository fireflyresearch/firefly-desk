# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for user memory agent tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from flydesk.memory.models import UserMemory
from flydesk.tools.builtin import BuiltinToolExecutor, BuiltinToolRegistry


class TestMemoryToolRegistry:
    def test_memory_tools_always_available(self):
        """Memory tools should be available even with no permissions."""
        tools = BuiltinToolRegistry.get_tool_definitions([])
        names = {t.name for t in tools}
        assert "save_memory" in names
        assert "recall_memories" in names


class TestSaveMemory:
    @pytest.fixture
    def executor(self):
        memory_repo = MagicMock()
        memory_repo.create = AsyncMock(
            return_value=UserMemory(
                id="mem-1",
                user_id="user-1",
                content="test",
                category="general",
                source="agent",
            )
        )
        exec_ = BuiltinToolExecutor(
            catalog_repo=MagicMock(),
            audit_logger=MagicMock(),
            memory_repo=memory_repo,
        )
        exec_.set_user_context("user-1")
        return exec_

    async def test_save_memory(self, executor):
        result = await executor.execute(
            "save_memory", {"content": "I prefer dark mode"}
        )
        assert result["memory_id"] == "mem-1"
        assert "saved" in result["message"].lower()

    async def test_save_memory_empty_content(self, executor):
        result = await executor.execute("save_memory", {"content": ""})
        assert "error" in result

    async def test_save_memory_no_user_context(self):
        exec_ = BuiltinToolExecutor(
            catalog_repo=MagicMock(),
            audit_logger=MagicMock(),
            memory_repo=MagicMock(),
        )
        result = await exec_.execute("save_memory", {"content": "test"})
        assert "error" in result


class TestRecallMemories:
    @pytest.fixture
    def executor(self):
        memory_repo = MagicMock()
        memory_repo.search = AsyncMock(
            return_value=[
                UserMemory(
                    id="mem-1",
                    user_id="user-1",
                    content="I prefer dark mode",
                    category="preference",
                    source="agent",
                )
            ]
        )
        exec_ = BuiltinToolExecutor(
            catalog_repo=MagicMock(),
            audit_logger=MagicMock(),
            memory_repo=memory_repo,
        )
        exec_.set_user_context("user-1")
        return exec_

    async def test_recall_memories(self, executor):
        result = await executor.execute(
            "recall_memories", {"query": "dark mode"}
        )
        assert result["count"] == 1
        assert result["memories"][0]["content"] == "I prefer dark mode"

    async def test_recall_empty_query(self, executor):
        result = await executor.execute("recall_memories", {"query": ""})
        assert "error" in result
