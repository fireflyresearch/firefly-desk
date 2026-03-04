# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for LLM runtime settings persistence and API endpoints."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.models.base import Base
from flydesk.settings.models import LLMRuntimeSettings
from flydesk.settings.repository import SettingsRepository


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
    return SettingsRepository(session_factory)


class TestLLMRuntimeRepository:
    async def test_get_defaults_when_empty(self, repo):
        """GET with no DB entries returns all defaults."""
        settings = await repo.get_llm_runtime_settings()
        assert isinstance(settings, LLMRuntimeSettings)
        assert settings.llm_max_retries == 3
        assert settings.llm_retry_base_delay == 3.0
        assert settings.llm_stream_timeout == 300
        assert settings.default_max_tokens == 4096
        assert settings.followup_max_content_chars == 8_000
        assert settings.file_context_max_per_file == 12_000
        assert settings.knowledge_analyzer_max_chars == 8_000
        assert settings.document_read_max_chars == 30_000

    async def test_put_and_get_roundtrip(self, repo):
        """PUT stores values, GET returns them."""
        custom = LLMRuntimeSettings(
            llm_max_retries=5,
            llm_retry_base_delay=5.0,
            llm_stream_timeout=600,
            default_max_tokens=8192,
            context_entity_limit=10,
        )
        await repo.set_llm_runtime_settings(custom)
        result = await repo.get_llm_runtime_settings()
        assert result.llm_max_retries == 5
        assert result.llm_retry_base_delay == 5.0
        assert result.llm_stream_timeout == 600
        assert result.default_max_tokens == 8192
        assert result.context_entity_limit == 10
        # Unmodified fields keep defaults
        assert result.llm_fallback_retries == 2
        assert result.followup_max_total_chars == 60_000

    async def test_knowledge_fields_roundtrip(self, repo):
        """PUT and GET the knowledge processing fields."""
        custom = LLMRuntimeSettings(
            knowledge_analyzer_max_chars=12_000,
            document_read_max_chars=50_000,
        )
        await repo.set_llm_runtime_settings(custom)
        result = await repo.get_llm_runtime_settings()
        assert result.knowledge_analyzer_max_chars == 12_000
        assert result.document_read_max_chars == 50_000
        # Other fields remain default
        assert result.llm_max_retries == 3

    async def test_partial_override(self, repo):
        """Only some fields in DB, rest use defaults."""
        await repo.set_app_setting(
            "llm_max_retries", "7", category="llm_runtime"
        )
        await repo.set_app_setting(
            "default_max_tokens", "16384", category="llm_runtime"
        )
        result = await repo.get_llm_runtime_settings()
        assert result.llm_max_retries == 7
        assert result.default_max_tokens == 16384
        # Everything else is default
        assert result.llm_retry_base_delay == 3.0
        assert result.llm_stream_timeout == 300


class TestDeskAgentLLMRuntimeCache:
    async def test_get_llm_runtime_no_repo(self):
        """Returns defaults when _settings_repo is None."""
        from unittest.mock import MagicMock

        from flydesk.agent.context import ContextEnricher
        from flydesk.agent.desk_agent import DeskAgent
        from flydesk.agent.prompt import SystemPromptBuilder
        from flydesk.widgets.parser import WidgetParser

        # Minimal DeskAgent with no settings_repo
        agent = DeskAgent(
            context_enricher=MagicMock(spec=ContextEnricher),
            prompt_builder=MagicMock(spec=SystemPromptBuilder),
            tool_factory=MagicMock(),
            widget_parser=MagicMock(spec=WidgetParser),
            audit_logger=MagicMock(),
            settings_repo=None,
        )
        rt = await agent._get_llm_runtime()
        assert isinstance(rt, LLMRuntimeSettings)
        assert rt.llm_max_retries == 3
        assert rt.default_max_tokens == 4096

    async def test_cache_invalidation(self, repo):
        """After setting _cached_llm_runtime to None, next call reloads from DB."""
        from unittest.mock import MagicMock

        from flydesk.agent.context import ContextEnricher
        from flydesk.agent.desk_agent import DeskAgent
        from flydesk.agent.prompt import SystemPromptBuilder
        from flydesk.widgets.parser import WidgetParser

        agent = DeskAgent(
            context_enricher=MagicMock(spec=ContextEnricher),
            prompt_builder=MagicMock(spec=SystemPromptBuilder),
            tool_factory=MagicMock(),
            widget_parser=MagicMock(spec=WidgetParser),
            audit_logger=MagicMock(),
            settings_repo=repo,
        )

        # First load — defaults (empty DB)
        rt = await agent._get_llm_runtime()
        assert rt.llm_max_retries == 3

        # Persist new value
        custom = LLMRuntimeSettings(llm_max_retries=10)
        await repo.set_llm_runtime_settings(custom)

        # Cache still returns old value
        rt_cached = await agent._get_llm_runtime()
        assert rt_cached.llm_max_retries == 3

        # Invalidate cache
        agent._cached_llm_runtime = None
        rt_reloaded = await agent._get_llm_runtime()
        assert rt_reloaded.llm_max_retries == 10
