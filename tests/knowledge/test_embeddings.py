# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for LLMEmbeddingProvider."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import httpx
import pytest

from flydesk.knowledge.embeddings import LLMEmbeddingProvider


class FakeLLMRepo:
    """Minimal stand-in for LLMProviderRepository."""

    def __init__(self, providers=None):
        self._providers = providers or []

    async def list_providers(self):
        return self._providers


class _FakeProviderType:
    """Stand-in for ProviderType enum with a .value attribute."""

    def __init__(self, value: str):
        self.value = value


class FakeProvider:
    """Minimal LLM provider stand-in."""

    def __init__(self, provider_type: str, api_key: str | None = None, name: str = "Test"):
        self.provider_type = _FakeProviderType(provider_type)
        self.api_key = api_key
        self.name = name


def _mock_openai_response(embeddings: list[list[float]]) -> httpx.Response:
    """Build a fake OpenAI-compatible embeddings response."""
    data = [{"embedding": emb, "index": i} for i, emb in enumerate(embeddings)]
    return httpx.Response(
        200,
        json={"data": data, "model": "text-embedding-3-small", "usage": {"total_tokens": 10}},
        request=httpx.Request("POST", "https://api.openai.com/v1/embeddings"),
    )


def _mock_google_response(embeddings: list[list[float]]) -> httpx.Response:
    """Build a fake Google batchEmbedContents response."""
    data = {"embeddings": [{"embedding": {"values": emb}} for emb in embeddings]}
    return httpx.Response(
        200,
        json=data,
        request=httpx.Request("POST", "https://example.com"),
    )


def _mock_ollama_response(embeddings: list[list[float]]) -> httpx.Response:
    """Build a fake Ollama embed response."""
    return httpx.Response(
        200,
        json={"embeddings": embeddings},
        request=httpx.Request("POST", "http://localhost:11434/api/embed"),
    )


class TestLLMEmbeddingProvider:
    def test_parse_model_string(self):
        """Provider and model are correctly parsed from 'provider:model' format."""
        provider = LLMEmbeddingProvider(
            http_client=httpx.AsyncClient(),
            embedding_model="openai:text-embedding-3-small",
            dimensions=1536,
            llm_repo=FakeLLMRepo(),
        )
        assert provider._provider == "openai"
        assert provider._model == "text-embedding-3-small"

    def test_invalid_model_string_raises(self):
        """Invalid model string without colon raises ValueError."""
        with pytest.raises(ValueError, match="provider:model"):
            LLMEmbeddingProvider(
                http_client=httpx.AsyncClient(),
                embedding_model="invalid-format",
                dimensions=1536,
                llm_repo=FakeLLMRepo(),
            )

    async def test_empty_input_returns_empty(self):
        """Empty text list returns empty embeddings."""
        provider = LLMEmbeddingProvider(
            http_client=httpx.AsyncClient(),
            embedding_model="openai:text-embedding-3-small",
            dimensions=1536,
            llm_repo=FakeLLMRepo(),
        )
        result = await provider.embed([])
        assert result == []

    async def test_no_api_key_returns_zero_vectors(self):
        """Without API key, returns zero vectors for graceful fallback."""
        provider = LLMEmbeddingProvider(
            http_client=httpx.AsyncClient(),
            embedding_model="openai:text-embedding-3-small",
            dimensions=4,
            llm_repo=FakeLLMRepo(),
        )
        result = await provider.embed(["test text"])
        assert len(result) == 1
        assert result[0] == [0.0, 0.0, 0.0, 0.0]

    async def test_resolves_key_from_explicit_config(self):
        """Explicit api_key is used first."""
        provider = LLMEmbeddingProvider(
            http_client=httpx.AsyncClient(),
            embedding_model="openai:text-embedding-3-small",
            dimensions=4,
            llm_repo=FakeLLMRepo(),
            api_key="sk-explicit-key",
        )
        key = await provider._resolve_api_key()
        assert key == "sk-explicit-key"

    async def test_resolves_key_from_llm_provider(self):
        """API key is resolved from matching LLM provider."""
        repo = FakeLLMRepo(
            providers=[FakeProvider("openai", api_key="sk-from-provider")]
        )
        provider = LLMEmbeddingProvider(
            http_client=httpx.AsyncClient(),
            embedding_model="openai:text-embedding-3-small",
            dimensions=4,
            llm_repo=repo,
        )
        key = await provider._resolve_api_key()
        assert key == "sk-from-provider"

    async def test_resolves_key_from_env(self, monkeypatch):
        """API key is resolved from environment variable as fallback."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
        provider = LLMEmbeddingProvider(
            http_client=httpx.AsyncClient(),
            embedding_model="openai:text-embedding-3-small",
            dimensions=4,
            llm_repo=FakeLLMRepo(),
        )
        key = await provider._resolve_api_key()
        assert key == "sk-from-env"

    async def test_openai_embed_calls_api(self):
        """OpenAI embedding calls the correct endpoint and returns vectors."""
        expected = [[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]]

        transport = httpx.MockTransport(
            lambda request: _mock_openai_response(expected)
        )
        client = httpx.AsyncClient(transport=transport)

        provider = LLMEmbeddingProvider(
            http_client=client,
            embedding_model="openai:text-embedding-3-small",
            dimensions=4,
            llm_repo=FakeLLMRepo(),
            api_key="sk-test",
        )
        result = await provider.embed(["text one", "text two"])

        assert len(result) == 2
        assert result[0] == expected[0]
        assert result[1] == expected[1]

    async def test_voyage_embed_calls_api(self):
        """Voyage AI embedding uses the correct base URL."""
        expected = [[0.1, 0.2, 0.3]]

        def handler(request: httpx.Request) -> httpx.Response:
            assert "voyageai.com" in str(request.url)
            return _mock_openai_response(expected)

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)

        provider = LLMEmbeddingProvider(
            http_client=client,
            embedding_model="voyage:voyage-3.5",
            dimensions=3,
            llm_repo=FakeLLMRepo(),
            api_key="pa-test",
        )
        result = await provider.embed(["test"])

        assert len(result) == 1
        assert result[0] == expected[0]

    async def test_google_embed_calls_api(self):
        """Google embedding calls batchEmbedContents endpoint."""
        expected = [[0.1, 0.2, 0.3]]

        transport = httpx.MockTransport(
            lambda request: _mock_google_response(expected)
        )
        client = httpx.AsyncClient(transport=transport)

        provider = LLMEmbeddingProvider(
            http_client=client,
            embedding_model="google:text-embedding-004",
            dimensions=3,
            llm_repo=FakeLLMRepo(),
            api_key="goog-test",
        )
        result = await provider.embed(["test"])

        assert len(result) == 1
        assert result[0] == expected[0]

    async def test_ollama_embed_calls_api(self):
        """Ollama embedding doesn't require API key."""
        expected = [[0.1, 0.2, 0.3]]

        transport = httpx.MockTransport(
            lambda request: _mock_ollama_response(expected)
        )
        client = httpx.AsyncClient(transport=transport)

        provider = LLMEmbeddingProvider(
            http_client=client,
            embedding_model="ollama:nomic-embed-text",
            dimensions=3,
            llm_repo=FakeLLMRepo(),
        )
        result = await provider.embed(["test"])

        assert len(result) == 1
        assert result[0] == expected[0]

    async def test_api_error_returns_zero_vectors(self):
        """HTTP error returns zero vectors instead of crashing."""
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                500,
                json={"error": "Internal Server Error"},
                request=request,
            )
        )
        client = httpx.AsyncClient(transport=transport)

        provider = LLMEmbeddingProvider(
            http_client=client,
            embedding_model="openai:text-embedding-3-small",
            dimensions=4,
            llm_repo=FakeLLMRepo(),
            api_key="sk-test",
        )
        result = await provider.embed(["test"])

        assert len(result) == 1
        assert result[0] == [0.0, 0.0, 0.0, 0.0]

    async def test_key_resolution_is_cached(self):
        """API key is resolved only once (cached after first call)."""
        repo = FakeLLMRepo(
            providers=[FakeProvider("openai", api_key="sk-cached")]
        )
        provider = LLMEmbeddingProvider(
            http_client=httpx.AsyncClient(),
            embedding_model="openai:text-embedding-3-small",
            dimensions=4,
            llm_repo=repo,
        )

        key1 = await provider._resolve_api_key()
        # Change the repo — should still get cached key
        repo._providers = []
        key2 = await provider._resolve_api_key()

        assert key1 == key2 == "sk-cached"
