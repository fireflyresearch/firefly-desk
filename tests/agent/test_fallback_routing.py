# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for LLM fallback routing in DeskAgentFactory.create_agent()."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from flydesk.agent.genai_bridge import DeskAgentFactory
from flydesk.config import DeskConfig
from flydesk.llm.models import LLMProvider, ProviderType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider(
    provider_type: ProviderType = ProviderType.OPENAI,
    *,
    api_key: str | None = "sk-test-key",
    default_model: str | None = "gpt-4o",
    base_url: str | None = None,
) -> LLMProvider:
    return LLMProvider(
        id="prov-1",
        name="Test Provider",
        provider_type=provider_type,
        api_key=api_key,
        default_model=default_model,
        base_url=base_url,
    )


def _make_config(*, fallback_models: dict[str, list[str]] | None = None) -> DeskConfig:
    env = {"FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///test.db"}
    with patch.dict(os.environ, env):
        cfg = DeskConfig()
    if fallback_models is not None:
        cfg.llm_fallback_models = fallback_models
    return cfg


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFallbackRouting:
    """Tests for LLM fallback routing in create_agent()."""

    @pytest.fixture
    def llm_repo(self) -> AsyncMock:
        repo = AsyncMock()
        repo.get_default_provider.return_value = _make_provider()
        return repo

    @patch("flydesk.agent.genai_bridge.FireflyAgent")
    async def test_primary_succeeds_no_fallback(self, mock_agent_cls, llm_repo, monkeypatch):
        """When primary model works, no fallback should be attempted."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        factory = DeskAgentFactory(llm_repo)

        result = await factory.create_agent("You are helpful.")

        # FireflyAgent called exactly once (the primary)
        assert mock_agent_cls.call_count == 1
        assert result is not None

    @patch("flydesk.agent.genai_bridge.FireflyAgent")
    async def test_primary_fails_uses_fallback(self, mock_agent_cls, llm_repo, monkeypatch):
        """When primary fails, factory should try fallback models."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        cfg = _make_config(fallback_models={"openai": ["gpt-4o-mini"]})
        factory = DeskAgentFactory(llm_repo, config=cfg)

        sentinel = MagicMock()
        # First call (primary) fails, second call (fallback) succeeds
        mock_agent_cls.side_effect = [RuntimeError("Primary unavailable"), sentinel]

        result = await factory.create_agent("You are helpful.")

        assert mock_agent_cls.call_count == 2
        # The fallback call should use the fallback model string
        fallback_call_kwargs = mock_agent_cls.call_args_list[1]
        assert fallback_call_kwargs.kwargs["model"] == "openai:gpt-4o-mini"
        assert result is sentinel

    @patch("flydesk.agent.genai_bridge.FireflyAgent")
    async def test_all_fallbacks_fail_raises(self, mock_agent_cls, llm_repo, monkeypatch):
        """When all models fail, factory should raise the last error."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        cfg = _make_config(fallback_models={"openai": ["gpt-4o-mini", "gpt-3.5-turbo"]})
        factory = DeskAgentFactory(llm_repo, config=cfg)

        mock_agent_cls.side_effect = RuntimeError("Provider unavailable")

        with pytest.raises(RuntimeError, match="Provider unavailable"):
            await factory.create_agent("You are helpful.")

        # Primary + 2 fallbacks = 3 calls
        assert mock_agent_cls.call_count == 3

    @patch("flydesk.agent.genai_bridge.FireflyAgent")
    async def test_no_fallbacks_configured_raises_original(self, mock_agent_cls, llm_repo, monkeypatch):
        """When no fallbacks configured, factory should raise original error."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        # No config means no fallbacks
        factory = DeskAgentFactory(llm_repo)

        mock_agent_cls.side_effect = RuntimeError("Primary unavailable")

        with pytest.raises(RuntimeError, match="Primary unavailable"):
            await factory.create_agent("You are helpful.")

        # Only the primary was tried
        assert mock_agent_cls.call_count == 1

    @patch("flydesk.agent.genai_bridge.FireflyAgent")
    async def test_fallback_preserves_system_prompt_and_tools(self, mock_agent_cls, llm_repo, monkeypatch):
        """Fallback agent should receive the same system_prompt and tools."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        cfg = _make_config(fallback_models={"openai": ["gpt-4o-mini"]})
        factory = DeskAgentFactory(llm_repo, config=cfg)

        sentinel = MagicMock()
        mock_agent_cls.side_effect = [RuntimeError("Primary down"), sentinel]

        mock_tool = lambda x: x  # noqa: E731
        result = await factory.create_agent("Custom prompt", tools=[mock_tool])

        assert result is sentinel
        fallback_kwargs = mock_agent_cls.call_args_list[1].kwargs
        assert fallback_kwargs["instructions"] == "Custom prompt"
        assert fallback_kwargs["tools"] == [mock_tool]

    @patch("flydesk.agent.genai_bridge.FireflyAgent")
    async def test_second_fallback_succeeds_after_first_fails(self, mock_agent_cls, llm_repo, monkeypatch):
        """If first fallback also fails, second fallback should be tried."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        cfg = _make_config(fallback_models={"openai": ["gpt-4o-mini", "gpt-3.5-turbo"]})
        factory = DeskAgentFactory(llm_repo, config=cfg)

        sentinel = MagicMock()
        mock_agent_cls.side_effect = [
            RuntimeError("Primary down"),
            RuntimeError("First fallback down"),
            sentinel,
        ]

        result = await factory.create_agent("You are helpful.")

        assert mock_agent_cls.call_count == 3
        assert result is sentinel
        # Third call should use second fallback
        third_call_kwargs = mock_agent_cls.call_args_list[2].kwargs
        assert third_call_kwargs["model"] == "openai:gpt-3.5-turbo"

    @patch("flydesk.agent.genai_bridge.FireflyAgent")
    async def test_empty_fallback_list_raises_original(self, mock_agent_cls, llm_repo, monkeypatch):
        """Config with empty fallback list for provider type raises original."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        # Fallback config exists but for a different provider type
        cfg = _make_config(fallback_models={"anthropic": ["claude-haiku-4-5-20251001"]})
        factory = DeskAgentFactory(llm_repo, config=cfg)

        mock_agent_cls.side_effect = RuntimeError("Primary unavailable")

        with pytest.raises(RuntimeError, match="Primary unavailable"):
            await factory.create_agent("You are helpful.")

        assert mock_agent_cls.call_count == 1
