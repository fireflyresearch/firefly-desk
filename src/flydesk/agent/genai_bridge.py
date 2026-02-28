# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Bridge between Firefly Desk LLM configuration and fireflyframework-genai FireflyAgent."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

from fireflyframework_genai.agents import FireflyAgent

if TYPE_CHECKING:
    from fireflyframework_genai.memory import MemoryManager

    from flydesk.config import DeskConfig
    from flydesk.llm.models import LLMProvider
    from flydesk.llm.repository import LLMProviderRepository

_logger = logging.getLogger(__name__)


def provider_to_model_string(provider: LLMProvider) -> str:
    """Convert a Desk LLMProvider to a pydantic-ai model string like 'openai:gpt-4o'."""
    from flydesk.domain.exceptions import ConfigurationError
    from flydesk.llm.models import ProviderType

    model_name = provider.default_model
    if not model_name:
        raise ConfigurationError(
            "No model configured for LLM provider. Set model_id or model_name."
        )

    match provider.provider_type:
        case ProviderType.OPENAI:
            return f"openai:{model_name}"
        case ProviderType.ANTHROPIC:
            return f"anthropic:{model_name}"
        case ProviderType.GOOGLE:
            return f"google-gla:{model_name}"
        case ProviderType.AZURE_OPENAI:
            # Azure needs base_url set as env or config, model string format differs
            return f"openai:{model_name}"
        case ProviderType.OLLAMA:
            return f"ollama:{model_name}"
        case _:
            return f"openai:{model_name}"


class DeskAgentFactory:
    """Creates FireflyAgent instances configured from Desk LLM providers."""

    def __init__(
        self,
        llm_repo: LLMProviderRepository,
        memory_manager: MemoryManager | None = None,
        config: DeskConfig | None = None,
    ) -> None:
        self._llm_repo = llm_repo
        self._memory_manager = memory_manager
        self._config = config

    # ------------------------------------------------------------------
    # Middleware construction
    # ------------------------------------------------------------------

    def _build_middleware(self) -> list[object]:
        """Build middleware list based on DeskConfig flags.

        Returns an empty list when no config is provided or all middleware
        features are disabled.
        """
        if self._config is None:
            return []

        middleware: list[object] = []

        if self._config.cost_guard_enabled:
            from fireflyframework_genai.agents.builtin_middleware import CostGuardMiddleware

            middleware.append(
                CostGuardMiddleware(
                    budget_usd=self._config.cost_guard_max_per_day,
                    per_call_limit_usd=self._config.cost_guard_max_per_message,
                )
            )

        if self._config.prompt_cache_enabled:
            from fireflyframework_genai.agents.prompt_cache import PromptCacheMiddleware

            middleware.append(
                PromptCacheMiddleware(cache_ttl_seconds=self._config.prompt_cache_ttl)
            )

        if self._config.circuit_breaker_enabled:
            from fireflyframework_genai.resilience.circuit_breaker import (
                CircuitBreakerMiddleware,
            )

            middleware.append(
                CircuitBreakerMiddleware(
                    failure_threshold=self._config.circuit_breaker_failure_threshold,
                    recovery_timeout=float(self._config.circuit_breaker_recovery_timeout),
                )
            )

        return middleware

    # ------------------------------------------------------------------
    # Agent creation
    # ------------------------------------------------------------------

    async def create_agent(
        self,
        system_prompt: str,
        tools: list[object] | None = None,
        model_settings_override: dict[str, Any] | None = None,
        model_override: str | None = None,
    ) -> FireflyAgent | None:
        """Create a FireflyAgent from the default LLM provider.

        Args:
            system_prompt: The system prompt for the agent.
            tools: Optional list of tools for the agent.
            model_settings_override: Optional model settings to merge.
            model_override: If provided, use this pydantic-ai model string
                instead of the provider's default model (e.g. for fallback).

        Returns None if no provider is configured or no API key is set.
        """
        try:
            provider = await self._llm_repo.get_default_provider()
        except Exception:
            _logger.debug("Failed to fetch LLM provider.", exc_info=True)
            return None

        if provider is None or not provider.api_key:
            return None

        model_str = model_override or provider_to_model_string(provider)

        # Set the API key in the environment for the provider
        # pydantic-ai reads API keys from standard env vars
        _set_provider_env(provider)

        middleware = self._build_middleware()

        # Determine max_tokens from provider capabilities or use sensible default.
        # The Anthropic API requires max_tokens; without it tool-use responses
        # may be truncated before the model can emit tool_use blocks.
        max_tokens = 4096
        if provider.models:
            caps = provider.models[0].capabilities
            if caps.max_output_tokens:
                max_tokens = caps.max_output_tokens

        settings: dict[str, Any] = {"max_tokens": max_tokens}
        if model_settings_override:
            settings.update(model_settings_override)

        if not tools:
            _logger.warning("Creating agent with NO tools — agent won't be able to call APIs")

        agent = FireflyAgent(
            name="ember",
            model=model_str,
            instructions=system_prompt,
            tools=tools or [],
            auto_register=False,
            default_middleware=False,  # We handle our own audit/logging
            memory=self._memory_manager,
            middleware=middleware if middleware else None,
            model_settings=settings,
        )

        # PydanticAI defaults to end_strategy='early' which skips pending
        # tool calls once a text result is produced.  Desk agents rely on
        # multiple tools executing in the same turn (e.g. knowledge_retrieval
        # + web_search), so we switch to 'exhaustive' to guarantee all
        # requested tool calls complete before the model responds.
        agent.agent.end_strategy = "exhaustive"  # type: ignore[assignment]

        return agent


    async def get_fallback_model_strings(self) -> list[str]:
        """Return fallback model strings for the default provider.

        These are lighter-weight models that can be used when the primary
        model is persistently overloaded.  Returns an empty list when no
        fallback models are defined for the provider type or no config is set.
        """
        if self._config is None:
            return []

        try:
            provider = await self._llm_repo.get_default_provider()
        except Exception:
            return []

        if provider is None:
            return []

        from flydesk.llm.models import ProviderType

        pt = provider.provider_type.value if hasattr(provider.provider_type, "value") else str(provider.provider_type)
        fallback_ids = self._config.llm_fallback_models.get(pt, [])

        prefix_map = {
            ProviderType.OPENAI: "openai",
            ProviderType.ANTHROPIC: "anthropic",
            ProviderType.GOOGLE: "google-gla",
            ProviderType.AZURE_OPENAI: "openai",
            ProviderType.OLLAMA: "ollama",
        }
        prefix = prefix_map.get(provider.provider_type, "openai")
        return [f"{prefix}:{m}" for m in fallback_ids]


def _set_provider_env(provider: LLMProvider) -> None:
    """Set environment variables for the provider's API key."""
    from flydesk.llm.models import ProviderType

    match provider.provider_type:
        case ProviderType.OPENAI | ProviderType.AZURE_OPENAI | ProviderType.OLLAMA:
            os.environ["OPENAI_API_KEY"] = provider.api_key
            if provider.base_url:
                os.environ["OPENAI_BASE_URL"] = provider.base_url
        case ProviderType.ANTHROPIC:
            os.environ["ANTHROPIC_API_KEY"] = provider.api_key
        case ProviderType.GOOGLE:
            os.environ["GOOGLE_API_KEY"] = provider.api_key
