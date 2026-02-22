# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for LLMHealthChecker."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from flydesk.llm.health import LLMHealthChecker
from flydesk.llm.models import LLMProvider, ProviderType


@pytest.fixture
def checker():
    return LLMHealthChecker()


@pytest.fixture
def openai_provider() -> LLMProvider:
    return LLMProvider(
        id="openai-1",
        name="OpenAI",
        provider_type=ProviderType.OPENAI,
        api_key="sk-test",
        base_url="https://api.openai.com/v1",
    )


@pytest.fixture
def ollama_provider() -> LLMProvider:
    return LLMProvider(
        id="ollama-1",
        name="Local Ollama",
        provider_type=ProviderType.OLLAMA,
        base_url="http://localhost:11434",
    )


class TestLLMHealthChecker:
    async def test_health_check_unreachable_provider(self, checker, openai_provider):
        """Verify that a connection failure returns reachable=False."""
        with patch("flydesk.llm.health.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await checker.check(openai_provider)

            assert result.reachable is False
            assert result.provider_id == "openai-1"
            assert result.error is not None
            assert result.latency_ms is not None

    async def test_health_check_successful(self, checker, openai_provider):
        """Verify that a successful HTTP response returns reachable=True."""
        mock_response = AsyncMock()
        mock_response.status_code = 200

        with patch("flydesk.llm.health.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await checker.check(openai_provider)

            assert result.reachable is True
            assert result.provider_id == "openai-1"
            assert result.latency_ms is not None

    async def test_health_check_http_error(self, checker, openai_provider):
        """Verify that a 4xx/5xx response returns reachable=False."""
        mock_response = AsyncMock()
        mock_response.status_code = 401

        with patch("flydesk.llm.health.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await checker.check(openai_provider)

            assert result.reachable is False
            assert "401" in (result.error or "")

    async def test_health_check_no_base_url(self, checker):
        """Verify that a provider without a base URL returns an error."""
        provider = LLMProvider(
            id="azure-1",
            name="Azure",
            provider_type=ProviderType.AZURE_OPENAI,
        )
        result = await checker.check(provider)
        assert result.reachable is False
        assert "No base URL" in (result.error or "")

    async def test_health_check_ollama(self, checker, ollama_provider):
        """Verify that Ollama health check uses the correct endpoint."""
        mock_response = AsyncMock()
        mock_response.status_code = 200

        with patch("flydesk.llm.health.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await checker.check(ollama_provider)

            assert result.reachable is True
            # Verify the URL includes /api/tags for Ollama
            call_args = mock_client.get.call_args
            assert "/api/tags" in call_args[0][0]
