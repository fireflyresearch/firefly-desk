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
from typing import TYPE_CHECKING

from fireflyframework_genai.agents import FireflyAgent

if TYPE_CHECKING:
    from fireflyframework_genai.memory import MemoryManager

    from flydesk.llm.models import LLMProvider
    from flydesk.llm.repository import LLMProviderRepository

_logger = logging.getLogger(__name__)


def provider_to_model_string(provider: LLMProvider) -> str:
    """Convert a Desk LLMProvider to a pydantic-ai model string like 'openai:gpt-4o'."""
    from flydesk.llm.models import ProviderType

    model_name = provider.default_model or "gpt-4o"

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
    ) -> None:
        self._llm_repo = llm_repo
        self._memory_manager = memory_manager

    async def create_agent(
        self,
        system_prompt: str,
        tools: list[object] | None = None,
    ) -> FireflyAgent | None:
        """Create a FireflyAgent from the default LLM provider.

        Returns None if no provider is configured or no API key is set.
        """
        try:
            provider = await self._llm_repo.get_default_provider()
        except Exception:
            _logger.debug("Failed to fetch LLM provider.", exc_info=True)
            return None

        if provider is None or not provider.api_key:
            return None

        model_str = provider_to_model_string(provider)

        # Set the API key in the environment for the provider
        # pydantic-ai reads API keys from standard env vars
        _set_provider_env(provider)

        return FireflyAgent(
            name="ember",
            model=model_str,
            instructions=system_prompt,
            tools=tools or [],
            auto_register=False,
            default_middleware=False,  # We handle our own audit/logging
            memory=self._memory_manager,
        )


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
