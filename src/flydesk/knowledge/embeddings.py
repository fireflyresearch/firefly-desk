# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Real embedding providers for knowledge retrieval.

Supports OpenAI, Voyage AI, Google, Ollama, and Azure OpenAI embedding APIs.
The provider is selected via the ``FLYDESK_EMBEDDING_MODEL`` config setting
(format: ``provider:model``, e.g. ``openai:text-embedding-3-small``).

API key resolution order:
1. Explicit ``FLYDESK_EMBEDDING_API_KEY`` config / env var
2. Matching LLM provider configured in the admin UI
3. Provider-specific env var (``OPENAI_API_KEY``, ``VOYAGE_API_KEY``, etc.)
4. Graceful fallback to zero-vector embeddings (keyword search still works)
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from flydesk.llm.repository import LLMProviderRepository

_logger = logging.getLogger(__name__)

# Default base URLs per embedding provider
_BASE_URLS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "voyage": "https://api.voyageai.com/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta",
    "ollama": "http://localhost:11434",
    "azure": "",  # requires explicit base_url
}

# Environment variable names per provider
_ENV_KEYS: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "voyage": "VOYAGE_API_KEY",
    "google": "GOOGLE_API_KEY",
    "azure": "AZURE_OPENAI_API_KEY",
}

# Map embedding provider names to LLM ProviderType values for key reuse
_LLM_PROVIDER_MAP: dict[str, str] = {
    "openai": "openai",
    "google": "google",
    "ollama": "ollama",
    "azure": "azure_openai",
}


class LLMEmbeddingProvider:
    """Generate real embeddings via OpenAI, Voyage AI, Google, or Ollama APIs.

    Implements the ``EmbeddingProvider`` protocol expected by
    ``KnowledgeIndexer`` and ``KnowledgeRetriever``.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        embedding_model: str,
        dimensions: int,
        llm_repo: LLMProviderRepository,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        parts = embedding_model.split(":", 1)
        if len(parts) != 2:
            raise ValueError(
                f"embedding_model must be 'provider:model', got: {embedding_model!r}"
            )

        self._provider = parts[0].lower()
        self._model = parts[1]
        self._dimensions = dimensions
        self._http_client = http_client
        self._llm_repo = llm_repo
        self._explicit_key = api_key
        self._base_url_override = base_url
        self._resolved_key: str | None = None
        self._key_resolved = False

    async def _resolve_api_key(self) -> str | None:
        """Resolve API key from explicit config, LLM providers, or environment."""
        if self._key_resolved:
            return self._resolved_key

        self._key_resolved = True

        # 1. Explicit key from config
        if self._explicit_key:
            self._resolved_key = self._explicit_key
            _logger.debug("Using explicit embedding API key from config.")
            return self._resolved_key

        # 2. From matching LLM provider registered in admin UI
        llm_type = _LLM_PROVIDER_MAP.get(self._provider)
        if llm_type:
            try:
                providers = await self._llm_repo.list_providers()
                for p in providers:
                    if p.provider_type.value == llm_type and p.api_key:
                        self._resolved_key = p.api_key
                        _logger.info(
                            "Using API key from LLM provider '%s' for embeddings.", p.name
                        )
                        return self._resolved_key
            except Exception:
                _logger.debug(
                    "Failed to fetch LLM providers for embedding key.", exc_info=True
                )

        # 3. Provider-specific environment variable
        env_var = _ENV_KEYS.get(self._provider)
        if env_var:
            key = os.environ.get(env_var)
            if key:
                self._resolved_key = key
                _logger.info("Using %s environment variable for embeddings.", env_var)
                return self._resolved_key

        _logger.warning(
            "No API key found for embedding provider '%s'. "
            "Configure a matching LLM provider in Admin > LLM Providers, "
            "set FLYDESK_EMBEDDING_API_KEY, or set %s. "
            "Falling back to zero-vector embeddings (keyword search only).",
            self._provider,
            _ENV_KEYS.get(self._provider, f"{self._provider.upper()}_API_KEY"),
        )
        return None

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for the given texts.

        Returns zero vectors if the API call fails or no API key is available,
        allowing the keyword-based retriever fallback to handle retrieval.
        """
        if not texts:
            return []

        api_key = await self._resolve_api_key()

        # Ollama runs locally and doesn't need an API key
        if not api_key and self._provider not in ("ollama",):
            return [[0.0] * self._dimensions for _ in texts]

        try:
            if self._provider in ("openai", "voyage", "azure"):
                return await self._embed_openai_compatible(texts, api_key)
            if self._provider == "google":
                return await self._embed_google(texts, api_key)
            if self._provider == "ollama":
                return await self._embed_ollama(texts)

            _logger.warning("Unknown embedding provider: %s", self._provider)
            return [[0.0] * self._dimensions for _ in texts]
        except httpx.HTTPStatusError as exc:
            _logger.error(
                "Embedding API returned HTTP %s for provider '%s': %s",
                exc.response.status_code,
                self._provider,
                exc.response.text[:200],
            )
            return [[0.0] * self._dimensions for _ in texts]
        except Exception:
            _logger.error(
                "Embedding API call failed for provider '%s'.",
                self._provider,
                exc_info=True,
            )
            return [[0.0] * self._dimensions for _ in texts]

    # ------------------------------------------------------------------
    # Provider-specific implementations
    # ------------------------------------------------------------------

    async def _embed_openai_compatible(
        self, texts: list[str], api_key: str | None
    ) -> list[list[float]]:
        """Call OpenAI-compatible ``/v1/embeddings`` endpoint.

        Works for OpenAI, Voyage AI, and Azure OpenAI — they all share the
        same request/response format.
        """
        base = self._base_url_override or _BASE_URLS.get(self._provider, _BASE_URLS["openai"])
        url = f"{base.rstrip('/')}/embeddings"

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        all_embeddings: list[list[float]] = []
        batch_size = 96  # safe batch size for all providers

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            payload: dict = {
                "input": batch,
                "model": self._model,
            }
            # OpenAI and Voyage support the dimensions parameter
            if self._provider in ("openai", "voyage") and self._dimensions:
                payload["dimensions"] = self._dimensions

            resp = await self._http_client.post(
                url, json=payload, headers=headers, timeout=30.0
            )
            resp.raise_for_status()
            data = resp.json()

            sorted_data = sorted(data["data"], key=lambda x: x["index"])
            all_embeddings.extend([item["embedding"] for item in sorted_data])

        return all_embeddings

    async def _embed_google(
        self, texts: list[str], api_key: str | None
    ) -> list[list[float]]:
        """Call Google Generative Language ``batchEmbedContents`` endpoint."""
        base = self._base_url_override or _BASE_URLS["google"]
        url = f"{base.rstrip('/')}/models/{self._model}:batchEmbedContents"
        if api_key:
            url = f"{url}?key={api_key}"

        all_embeddings: list[list[float]] = []
        batch_size = 100

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            requests_list = [
                {
                    "model": f"models/{self._model}",
                    "content": {"parts": [{"text": t}]},
                }
                for t in batch
            ]

            resp = await self._http_client.post(
                url,
                json={"requests": requests_list},
                headers={"Content-Type": "application/json"},
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()

            all_embeddings.extend(
                [item["embedding"]["values"] for item in data["embeddings"]]
            )

        return all_embeddings

    async def _embed_ollama(self, texts: list[str]) -> list[list[float]]:
        """Call Ollama local ``/api/embed`` endpoint."""
        base = self._base_url_override or _BASE_URLS["ollama"]
        url = f"{base.rstrip('/')}/api/embed"

        all_embeddings: list[list[float]] = []
        batch_size = 50  # Ollama batches can be smaller for local models

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            resp = await self._http_client.post(
                url,
                json={"model": self._model, "input": batch},
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()

            all_embeddings.extend(data["embeddings"])

        return all_embeddings
