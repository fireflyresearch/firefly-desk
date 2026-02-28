# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Factory for creating genai embedders from configuration strings.

Config format: "provider:model" (e.g., "openai:text-embedding-3-small").
"""

from __future__ import annotations

from typing import Any

from fireflyframework_genai.embeddings import BaseEmbedder
from fireflyframework_genai.embeddings.providers import (
    AzureEmbedder,
    BedrockEmbedder,
    CohereEmbedder,
    GoogleEmbedder,
    MistralEmbedder,
    OllamaEmbedder,
    OpenAIEmbedder,
    VoyageEmbedder,
)

from flydesk.domain.exceptions import ConfigurationError, ProviderNotFoundError

_PROVIDER_MAP: dict[str, type[BaseEmbedder]] = {
    "openai": OpenAIEmbedder,
    "azure": AzureEmbedder,
    "bedrock": BedrockEmbedder,
    "cohere": CohereEmbedder,
    "google": GoogleEmbedder,
    "mistral": MistralEmbedder,
    "ollama": OllamaEmbedder,
    "voyage": VoyageEmbedder,
}


def parse_embedding_config(config_string: str) -> tuple[str, str]:
    """Parse a 'provider:model' config string into (provider, model).

    Raises :class:`ConfigurationError` if the string doesn't contain a colon
    separator.
    """
    if not config_string or ":" not in config_string:
        raise ConfigurationError(
            f"Invalid embedding_model format: {config_string!r}. "
            "Expected 'provider:model' (e.g., 'openai:text-embedding-3-small')."
        )
    provider, _, model = config_string.partition(":")
    return provider.strip().lower(), model.strip()


def create_embedder(
    provider: str,
    model: str,
    *,
    dimensions: int | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    **kwargs: Any,
) -> BaseEmbedder:
    """Instantiate the correct genai embedder for the given provider.

    Raises :class:`ProviderNotFoundError` if the provider is not supported.
    """
    cls = _PROVIDER_MAP.get(provider.lower())
    if cls is None:
        supported = ", ".join(sorted(_PROVIDER_MAP))
        raise ProviderNotFoundError(
            f"Unknown embedding provider: {provider!r}. Supported: {supported}"
        )

    init_kwargs: dict[str, Any] = {"model": model}
    if dimensions is not None:
        init_kwargs["dimensions"] = dimensions
    if api_key is not None:
        init_kwargs["api_key"] = api_key
    if provider.lower() == "ollama" and base_url:
        init_kwargs["base_url"] = base_url
    elif provider.lower() == "azure" and base_url:
        init_kwargs["azure_endpoint"] = base_url
    init_kwargs.update(kwargs)
    return cls(**init_kwargs)
