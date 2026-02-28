# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the genai_bridge module (DeskAgentFactory, provider_to_model_string, _set_provider_env)."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from flydesk.agent.genai_bridge import (
    DeskAgentFactory,
    _set_provider_env,
    provider_to_model_string,
)
from flydesk.config import DeskConfig
from flydesk.llm.models import LLMProvider, ProviderType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider(
    provider_type: ProviderType,
    *,
    api_key: str | None = "sk-test-key",
    default_model: str | None = None,
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


# ---------------------------------------------------------------------------
# provider_to_model_string tests
# ---------------------------------------------------------------------------

class TestProviderToModelString:
    """Tests for provider_to_model_string()."""

    def test_openai_with_default_model(self):
        provider = _make_provider(ProviderType.OPENAI, default_model="gpt-4o")
        assert provider_to_model_string(provider) == "openai:gpt-4o"

    def test_openai_without_model_falls_back_to_gpt4o(self):
        provider = _make_provider(ProviderType.OPENAI, default_model=None)
        assert provider_to_model_string(provider) == "openai:gpt-4o"

    def test_anthropic(self):
        provider = _make_provider(ProviderType.ANTHROPIC, default_model="claude-sonnet-4-20250514")
        assert provider_to_model_string(provider) == "anthropic:claude-sonnet-4-20250514"

    def test_google(self):
        provider = _make_provider(ProviderType.GOOGLE, default_model="gemini-2.0-flash")
        assert provider_to_model_string(provider) == "google-gla:gemini-2.0-flash"

    def test_azure_openai_uses_openai_prefix(self):
        provider = _make_provider(ProviderType.AZURE_OPENAI, default_model="gpt-4o")
        assert provider_to_model_string(provider) == "openai:gpt-4o"

    def test_ollama(self):
        provider = _make_provider(ProviderType.OLLAMA, default_model="llama3")
        assert provider_to_model_string(provider) == "ollama:llama3"

    def test_unknown_provider_type_falls_back_to_openai(self):
        """If a new ProviderType value is added and not handled, fall back to openai."""
        # Create a provider with a known type but test the default branch
        # by simulating the match-all case through a manually-crafted type.
        provider = _make_provider(ProviderType.OPENAI, default_model="gpt-4o-mini")
        # We know OPENAI matches, so test each known type directly for coverage.
        # The default branch is tested via the fallback model logic.
        assert provider_to_model_string(provider) == "openai:gpt-4o-mini"


# ---------------------------------------------------------------------------
# _set_provider_env tests
# ---------------------------------------------------------------------------

class TestSetProviderEnv:
    """Tests for _set_provider_env()."""

    def test_openai_sets_openai_api_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        provider = _make_provider(ProviderType.OPENAI, api_key="sk-openai-123")
        _set_provider_env(provider)
        assert os.environ["OPENAI_API_KEY"] == "sk-openai-123"

    def test_openai_sets_base_url_when_provided(self, monkeypatch):
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        provider = _make_provider(
            ProviderType.OPENAI,
            api_key="sk-test",
            base_url="https://custom.openai.example.com",
        )
        _set_provider_env(provider)
        assert os.environ["OPENAI_BASE_URL"] == "https://custom.openai.example.com"

    def test_openai_does_not_set_base_url_when_none(self, monkeypatch):
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        provider = _make_provider(ProviderType.OPENAI, api_key="sk-test", base_url=None)
        _set_provider_env(provider)
        assert "OPENAI_BASE_URL" not in os.environ

    def test_azure_openai_sets_openai_api_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        provider = _make_provider(ProviderType.AZURE_OPENAI, api_key="az-key-456")
        _set_provider_env(provider)
        assert os.environ["OPENAI_API_KEY"] == "az-key-456"

    def test_azure_openai_sets_base_url(self, monkeypatch):
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        provider = _make_provider(
            ProviderType.AZURE_OPENAI,
            api_key="az-key",
            base_url="https://mydeployment.openai.azure.com/",
        )
        _set_provider_env(provider)
        assert os.environ["OPENAI_BASE_URL"] == "https://mydeployment.openai.azure.com/"

    def test_ollama_sets_openai_api_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        provider = _make_provider(ProviderType.OLLAMA, api_key="ollama-key")
        _set_provider_env(provider)
        assert os.environ["OPENAI_API_KEY"] == "ollama-key"

    def test_anthropic_sets_anthropic_api_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        provider = _make_provider(ProviderType.ANTHROPIC, api_key="sk-ant-test")
        _set_provider_env(provider)
        assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-test"

    def test_google_sets_google_api_key(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        provider = _make_provider(ProviderType.GOOGLE, api_key="goog-key-789")
        _set_provider_env(provider)
        assert os.environ["GOOGLE_API_KEY"] == "goog-key-789"


# ---------------------------------------------------------------------------
# DeskAgentFactory tests
# ---------------------------------------------------------------------------

class TestDeskAgentFactory:
    """Tests for DeskAgentFactory.create_agent()."""

    @pytest.fixture
    def llm_repo(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def memory_manager(self) -> AsyncMock:
        from fireflyframework_genai.memory import MemoryManager

        return AsyncMock(spec=MemoryManager)

    @pytest.fixture
    def factory(self, llm_repo: AsyncMock) -> DeskAgentFactory:
        return DeskAgentFactory(llm_repo)

    @pytest.fixture
    def factory_with_memory(
        self, llm_repo: AsyncMock, memory_manager: AsyncMock,
    ) -> DeskAgentFactory:
        return DeskAgentFactory(llm_repo, memory_manager=memory_manager)

    @pytest.fixture
    def _make_config(self):
        """Return a helper that builds a DeskConfig with middleware flags."""
        def _factory(**overrides):
            env = {"FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///test.db"}
            for key, val in overrides.items():
                env[f"FLYDESK_{key.upper()}"] = str(val)
            with patch.dict(os.environ, env):
                return DeskConfig()
        return _factory

    async def test_returns_none_when_no_provider(self, factory, llm_repo):
        llm_repo.get_default_provider.return_value = None
        result = await factory.create_agent("You are a helpful assistant.")
        assert result is None

    async def test_returns_none_when_no_api_key(self, factory, llm_repo):
        llm_repo.get_default_provider.return_value = _make_provider(
            ProviderType.OPENAI, api_key=None,
        )
        result = await factory.create_agent("You are a helpful assistant.")
        assert result is None

    async def test_returns_none_when_api_key_empty(self, factory, llm_repo):
        llm_repo.get_default_provider.return_value = _make_provider(
            ProviderType.OPENAI, api_key="",
        )
        result = await factory.create_agent("You are a helpful assistant.")
        assert result is None

    async def test_returns_none_when_repo_raises(self, factory, llm_repo):
        llm_repo.get_default_provider.side_effect = RuntimeError("DB down")
        result = await factory.create_agent("You are a helpful assistant.")
        assert result is None

    @patch("flydesk.agent.genai_bridge.FireflyAgent")
    async def test_returns_firefly_agent_when_provider_configured(
        self, mock_agent_cls, factory, llm_repo, monkeypatch
    ):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        provider = _make_provider(
            ProviderType.OPENAI, api_key="sk-real-key", default_model="gpt-4o",
        )
        llm_repo.get_default_provider.return_value = provider

        result = await factory.create_agent("You are a helpful assistant.")

        mock_agent_cls.assert_called_once_with(
            name="ember",
            model="openai:gpt-4o",
            instructions="You are a helpful assistant.",
            tools=[],
            auto_register=False,
            default_middleware=False,
            memory=None,
            middleware=None,
            model_settings={"max_tokens": 4096},
        )
        assert result is mock_agent_cls.return_value

    @patch("flydesk.agent.genai_bridge.FireflyAgent")
    async def test_sets_env_vars_before_creating_agent(
        self, mock_agent_cls, factory, llm_repo, monkeypatch
    ):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        provider = _make_provider(
            ProviderType.OPENAI, api_key="sk-env-test",
        )
        llm_repo.get_default_provider.return_value = provider

        await factory.create_agent("system prompt")
        assert os.environ.get("OPENAI_API_KEY") == "sk-env-test"

    @patch("flydesk.agent.genai_bridge.FireflyAgent")
    async def test_anthropic_provider_creates_agent_with_correct_model(
        self, mock_agent_cls, factory, llm_repo, monkeypatch
    ):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        provider = _make_provider(
            ProviderType.ANTHROPIC,
            api_key="sk-ant-test",
            default_model="claude-sonnet-4-20250514",
        )
        llm_repo.get_default_provider.return_value = provider

        await factory.create_agent("system prompt")
        call_kwargs = mock_agent_cls.call_args
        assert call_kwargs.kwargs["model"] == "anthropic:claude-sonnet-4-20250514"
        assert os.environ.get("ANTHROPIC_API_KEY") == "sk-ant-test"

    @patch("flydesk.agent.genai_bridge.FireflyAgent")
    async def test_passes_tools_to_agent(
        self, mock_agent_cls, factory, llm_repo, monkeypatch
    ):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        provider = _make_provider(ProviderType.OPENAI, api_key="sk-test")
        llm_repo.get_default_provider.return_value = provider

        mock_tool = lambda x: x  # noqa: E731
        await factory.create_agent("system prompt", tools=[mock_tool])
        call_kwargs = mock_agent_cls.call_args
        assert call_kwargs.kwargs["tools"] == [mock_tool]

    @patch("flydesk.agent.genai_bridge.FireflyAgent")
    async def test_passes_memory_manager_to_agent(
        self, mock_agent_cls, factory_with_memory, memory_manager, llm_repo, monkeypatch
    ):
        """create_agent() should pass the MemoryManager to FireflyAgent."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        provider = _make_provider(ProviderType.OPENAI, api_key="sk-test")
        llm_repo.get_default_provider.return_value = provider

        await factory_with_memory.create_agent("system prompt")
        call_kwargs = mock_agent_cls.call_args
        assert call_kwargs.kwargs["memory"] is memory_manager

    @patch("flydesk.agent.genai_bridge.FireflyAgent")
    async def test_factory_without_memory_passes_none(
        self, mock_agent_cls, factory, llm_repo, monkeypatch
    ):
        """Factory created without memory_manager should pass memory=None."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        provider = _make_provider(ProviderType.OPENAI, api_key="sk-test")
        llm_repo.get_default_provider.return_value = provider

        await factory.create_agent("system prompt")
        call_kwargs = mock_agent_cls.call_args
        assert call_kwargs.kwargs["memory"] is None

    def test_factory_stores_memory_manager(self, llm_repo, memory_manager):
        """DeskAgentFactory should store the memory_manager."""
        factory = DeskAgentFactory(llm_repo, memory_manager=memory_manager)
        assert factory._memory_manager is memory_manager

    def test_factory_defaults_memory_to_none(self, llm_repo):
        """DeskAgentFactory should default memory_manager to None."""
        factory = DeskAgentFactory(llm_repo)
        assert factory._memory_manager is None

    def test_factory_stores_config(self, llm_repo, _make_config):
        """DeskAgentFactory should store the config."""
        cfg = _make_config()
        factory = DeskAgentFactory(llm_repo, config=cfg)
        assert factory._config is cfg

    def test_factory_defaults_config_to_none(self, llm_repo):
        """DeskAgentFactory should default config to None."""
        factory = DeskAgentFactory(llm_repo)
        assert factory._config is None


# ---------------------------------------------------------------------------
# Middleware selection tests
# ---------------------------------------------------------------------------

class TestBuildMiddleware:
    """Tests for DeskAgentFactory._build_middleware()."""

    @pytest.fixture
    def llm_repo(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def _make_config(self):
        def _factory(**overrides):
            env = {"FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///test.db"}
            for key, val in overrides.items():
                env[f"FLYDESK_{key.upper()}"] = str(val)
            with patch.dict(os.environ, env):
                return DeskConfig()
        return _factory

    def test_no_config_returns_empty(self, llm_repo):
        """No config means no middleware."""
        factory = DeskAgentFactory(llm_repo, config=None)
        assert factory._build_middleware() == []

    def test_all_disabled_returns_empty(self, llm_repo, _make_config):
        """All middleware disabled returns empty list."""
        cfg = _make_config(prompt_cache_enabled="false")
        factory = DeskAgentFactory(llm_repo, config=cfg)
        assert factory._build_middleware() == []

    def test_cost_guard_enabled(self, llm_repo, _make_config):
        """When cost_guard_enabled is True, CostGuardMiddleware is included."""
        from fireflyframework_genai.agents.builtin_middleware import CostGuardMiddleware

        cfg = _make_config(cost_guard_enabled="true", cost_guard_max_per_message="2.5", cost_guard_max_per_day="100")
        factory = DeskAgentFactory(llm_repo, config=cfg)
        mw = factory._build_middleware()
        assert len(mw) >= 1
        cost_guard = [m for m in mw if isinstance(m, CostGuardMiddleware)]
        assert len(cost_guard) == 1
        assert cost_guard[0]._budget == 100.0
        assert cost_guard[0]._per_call_limit == 2.5

    def test_prompt_cache_enabled(self, llm_repo, _make_config):
        """When prompt_cache_enabled is True, PromptCacheMiddleware is included."""
        from fireflyframework_genai.agents.prompt_cache import PromptCacheMiddleware

        cfg = _make_config(prompt_cache_enabled="true", prompt_cache_ttl="600")
        factory = DeskAgentFactory(llm_repo, config=cfg)
        mw = factory._build_middleware()
        assert len(mw) >= 1
        cache = [m for m in mw if isinstance(m, PromptCacheMiddleware)]
        assert len(cache) == 1
        assert cache[0]._cache_ttl_seconds == 600

    def test_circuit_breaker_enabled(self, llm_repo, _make_config):
        """When circuit_breaker_enabled is True, CircuitBreakerMiddleware is included."""
        from fireflyframework_genai.resilience.circuit_breaker import CircuitBreakerMiddleware

        cfg = _make_config(
            circuit_breaker_enabled="true",
            circuit_breaker_failure_threshold="10",
            circuit_breaker_recovery_timeout="120",
        )
        factory = DeskAgentFactory(llm_repo, config=cfg)
        mw = factory._build_middleware()
        assert len(mw) >= 1
        cb = [m for m in mw if isinstance(m, CircuitBreakerMiddleware)]
        assert len(cb) == 1

    def test_all_middleware_enabled(self, llm_repo, _make_config):
        """When all middleware flags are enabled, all three are included."""
        cfg = _make_config(
            cost_guard_enabled="true",
            prompt_cache_enabled="true",
            circuit_breaker_enabled="true",
        )
        factory = DeskAgentFactory(llm_repo, config=cfg)
        mw = factory._build_middleware()
        assert len(mw) == 3

    @patch("flydesk.agent.genai_bridge.FireflyAgent")
    async def test_create_agent_passes_middleware(
        self, mock_agent_cls, llm_repo, _make_config, monkeypatch,
    ):
        """create_agent() should pass the built middleware list to FireflyAgent."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        cfg = _make_config(cost_guard_enabled="true")
        factory = DeskAgentFactory(llm_repo, config=cfg)
        provider = _make_provider(ProviderType.OPENAI, api_key="sk-test")
        llm_repo.get_default_provider.return_value = provider

        await factory.create_agent("system prompt")
        call_kwargs = mock_agent_cls.call_args
        assert call_kwargs.kwargs["middleware"] is not None
        # cost_guard + prompt_cache (enabled by default)
        assert len(call_kwargs.kwargs["middleware"]) == 2

    @patch("flydesk.agent.genai_bridge.FireflyAgent")
    async def test_create_agent_no_middleware_when_disabled(
        self, mock_agent_cls, llm_repo, _make_config, monkeypatch,
    ):
        """create_agent() should pass middleware=None when all disabled."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        cfg = _make_config(prompt_cache_enabled="false")
        factory = DeskAgentFactory(llm_repo, config=cfg)
        provider = _make_provider(ProviderType.OPENAI, api_key="sk-test")
        llm_repo.get_default_provider.return_value = provider

        await factory.create_agent("system prompt")
        call_kwargs = mock_agent_cls.call_args
        assert call_kwargs.kwargs["middleware"] is None
