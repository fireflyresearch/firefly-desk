# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for model ID validation in the test-llm endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from flydesk.llm.health import LLMHealthChecker
from flydesk.llm.models import LLMProvider, ProviderType


@pytest.fixture
def checker():
    return LLMHealthChecker()


def _make_response(status_code: int, json_data: dict | None = None):
    """Create a mock httpx.Response (synchronous .json())."""
    resp = MagicMock()
    resp.status_code = status_code
    if json_data is not None:
        resp.json.return_value = json_data
    return resp


def _make_mock_client(response):
    """Create a mock httpx.AsyncClient that returns the given response."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestListModels:
    """Tests for LLMHealthChecker.list_models()."""

    async def test_openai_format(self, checker):
        """OpenAI-compatible response with data[] array returns model IDs."""
        resp = _make_response(200, {
            "data": [
                {"id": "gpt-4", "object": "model"},
                {"id": "gpt-4o", "object": "model"},
                {"id": "gpt-3.5-turbo", "object": "model"},
            ]
        })

        provider = LLMProvider(
            id="test",
            name="OpenAI",
            provider_type=ProviderType.OPENAI,
            api_key="sk-test",
        )

        with patch("flydesk.llm.health.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _make_mock_client(resp)
            models = await checker.list_models(provider)

        assert models == ["gpt-4", "gpt-4o", "gpt-3.5-turbo"]

    async def test_ollama_format(self, checker):
        """Ollama response with models[] array returns model names."""
        resp = _make_response(200, {
            "models": [
                {"name": "llama3", "size": 4000000000},
                {"name": "mistral", "size": 3000000000},
            ]
        })

        provider = LLMProvider(
            id="test",
            name="Ollama",
            provider_type=ProviderType.OLLAMA,
            base_url="http://localhost:11434",
        )

        with patch("flydesk.llm.health.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _make_mock_client(resp)
            models = await checker.list_models(provider)

        assert models == ["llama3", "mistral"]

    async def test_http_error_returns_empty(self, checker):
        """HTTP 4xx/5xx responses return an empty list."""
        resp = _make_response(401)

        provider = LLMProvider(
            id="test",
            name="OpenAI",
            provider_type=ProviderType.OPENAI,
            api_key="bad-key",
        )

        with patch("flydesk.llm.health.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _make_mock_client(resp)
            models = await checker.list_models(provider)

        assert models == []

    async def test_no_base_url_returns_empty(self, checker):
        """Provider with no base URL returns an empty list."""
        provider = LLMProvider(
            id="test",
            name="Azure",
            provider_type=ProviderType.AZURE_OPENAI,
            # No base_url and AZURE_OPENAI has empty default
        )

        models = await checker.list_models(provider)
        assert models == []

    async def test_network_error_returns_empty(self, checker):
        """Network exceptions return an empty list (no crash)."""
        import httpx

        provider = LLMProvider(
            id="test",
            name="OpenAI",
            provider_type=ProviderType.OPENAI,
            api_key="sk-test",
        )

        with patch("flydesk.llm.health.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            models = await checker.list_models(provider)

        assert models == []

    async def test_anthropic_headers(self, checker):
        """Anthropic provider uses x-api-key header."""
        resp = _make_response(200, {
            "data": [{"id": "claude-sonnet-4-20250514"}]
        })

        provider = LLMProvider(
            id="test",
            name="Anthropic",
            provider_type=ProviderType.ANTHROPIC,
            api_key="sk-ant-test",
        )

        with patch("flydesk.llm.health.httpx.AsyncClient") as mock_cls:
            mock_client = _make_mock_client(resp)
            mock_cls.return_value = mock_client
            await checker.list_models(provider)

            call_args = mock_client.get.call_args
            headers = call_args[1].get("headers", call_args.kwargs.get("headers", {}))
            assert headers["x-api-key"] == "sk-ant-test"

    async def test_google_api_key_in_url(self, checker):
        """Google provider appends key= query parameter to URL."""
        resp = _make_response(200, {"models": []})

        provider = LLMProvider(
            id="test",
            name="Google",
            provider_type=ProviderType.GOOGLE,
            api_key="google-key",
        )

        with patch("flydesk.llm.health.httpx.AsyncClient") as mock_cls:
            mock_client = _make_mock_client(resp)
            mock_cls.return_value = mock_client
            await checker.list_models(provider)

            call_args = mock_client.get.call_args
            url = call_args[0][0]
            assert "key=google-key" in url

    async def test_unknown_response_format_returns_empty(self, checker):
        """Unrecognized JSON structure returns an empty list."""
        resp = _make_response(200, {"results": [{"name": "x"}]})

        provider = LLMProvider(
            id="test",
            name="OpenAI",
            provider_type=ProviderType.OPENAI,
            api_key="sk-test",
        )

        with patch("flydesk.llm.health.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _make_mock_client(resp)
            models = await checker.list_models(provider)

        assert models == []


class TestTestLLMModelValidation:
    """Tests for model_id validation in POST /api/setup/test-llm."""

    async def test_valid_model_found(self):
        """When model_id exists in provider's model list, return reachable with no error."""
        from flydesk.api.setup import LLMTestRequest, test_llm_provider
        from flydesk.llm.models import ProviderHealthStatus

        health = ProviderHealthStatus(
            provider_id="__setup_test__",
            name="Setup Test",
            reachable=True,
            latency_ms=42.0,
            checked_at="2026-01-01T00:00:00Z",
        )

        with patch("flydesk.llm.health.LLMHealthChecker") as MockChecker:
            instance = MockChecker.return_value
            instance.check = AsyncMock(return_value=health)
            instance.list_models = AsyncMock(return_value=["gpt-4", "gpt-4o", "gpt-3.5-turbo"])

            body = LLMTestRequest(provider_type="openai", api_key="sk-test", model_id="gpt-4")
            result = await test_llm_provider(body)

        assert result.reachable is True
        assert result.error is None

    async def test_invalid_model_not_found(self):
        """When model_id does not exist in provider's model list, return error with 'not found'."""
        from flydesk.api.setup import LLMTestRequest, test_llm_provider
        from flydesk.llm.models import ProviderHealthStatus

        health = ProviderHealthStatus(
            provider_id="__setup_test__",
            name="Setup Test",
            reachable=True,
            latency_ms=42.0,
            checked_at="2026-01-01T00:00:00Z",
        )

        with patch("flydesk.llm.health.LLMHealthChecker") as MockChecker:
            instance = MockChecker.return_value
            instance.check = AsyncMock(return_value=health)
            instance.list_models = AsyncMock(return_value=["gpt-4", "gpt-4o"])

            body = LLMTestRequest(provider_type="openai", api_key="sk-test", model_id="gpt-99")
            result = await test_llm_provider(body)

        assert result.reachable is True
        assert result.error is not None
        assert "not found" in result.error
        assert "gpt-99" in result.error
        assert "gpt-4" in result.error  # Available models listed

    async def test_no_model_id_skips_validation(self):
        """When no model_id is provided, validation is skipped (backwards compatible)."""
        from flydesk.api.setup import LLMTestRequest, test_llm_provider
        from flydesk.llm.models import ProviderHealthStatus

        health = ProviderHealthStatus(
            provider_id="__setup_test__",
            name="Setup Test",
            reachable=True,
            latency_ms=42.0,
            checked_at="2026-01-01T00:00:00Z",
        )

        with patch("flydesk.llm.health.LLMHealthChecker") as MockChecker:
            instance = MockChecker.return_value
            instance.check = AsyncMock(return_value=health)
            # list_models should NOT be called when model_id is None
            instance.list_models = AsyncMock(return_value=["gpt-4"])

            body = LLMTestRequest(provider_type="openai", api_key="sk-test")
            result = await test_llm_provider(body)

        assert result.reachable is True
        assert result.error is None
        instance.list_models.assert_not_called()

    async def test_empty_model_list_skips_validation(self):
        """When list_models returns empty, skip validation (don't block the user)."""
        from flydesk.api.setup import LLMTestRequest, test_llm_provider
        from flydesk.llm.models import ProviderHealthStatus

        health = ProviderHealthStatus(
            provider_id="__setup_test__",
            name="Setup Test",
            reachable=True,
            latency_ms=42.0,
            checked_at="2026-01-01T00:00:00Z",
        )

        with patch("flydesk.llm.health.LLMHealthChecker") as MockChecker:
            instance = MockChecker.return_value
            instance.check = AsyncMock(return_value=health)
            instance.list_models = AsyncMock(return_value=[])

            body = LLMTestRequest(provider_type="openai", api_key="sk-test", model_id="gpt-99")
            result = await test_llm_provider(body)

        assert result.reachable is True
        assert result.error is None

    async def test_unreachable_provider_skips_model_validation(self):
        """When provider is unreachable, model validation is not attempted."""
        from flydesk.api.setup import LLMTestRequest, test_llm_provider
        from flydesk.llm.models import ProviderHealthStatus

        health = ProviderHealthStatus(
            provider_id="__setup_test__",
            name="Setup Test",
            reachable=False,
            latency_ms=100.0,
            error="Connection refused",
            checked_at="2026-01-01T00:00:00Z",
        )

        with patch("flydesk.llm.health.LLMHealthChecker") as MockChecker:
            instance = MockChecker.return_value
            instance.check = AsyncMock(return_value=health)
            instance.list_models = AsyncMock(return_value=["gpt-4"])

            body = LLMTestRequest(provider_type="openai", api_key="sk-test", model_id="gpt-4")
            result = await test_llm_provider(body)

        assert result.reachable is False
        assert result.error is not None
        instance.list_models.assert_not_called()

    async def test_model_id_with_whitespace_is_trimmed(self):
        """Model ID with surrounding whitespace should be trimmed before comparison."""
        from flydesk.api.setup import LLMTestRequest, test_llm_provider
        from flydesk.llm.models import ProviderHealthStatus

        health = ProviderHealthStatus(
            provider_id="__setup_test__",
            name="Setup Test",
            reachable=True,
            latency_ms=42.0,
            checked_at="2026-01-01T00:00:00Z",
        )

        with patch("flydesk.llm.health.LLMHealthChecker") as MockChecker:
            instance = MockChecker.return_value
            instance.check = AsyncMock(return_value=health)
            instance.list_models = AsyncMock(return_value=["gpt-4", "gpt-4o"])

            body = LLMTestRequest(provider_type="openai", api_key="sk-test", model_id="  gpt-4  ")
            result = await test_llm_provider(body)

        assert result.reachable is True
        assert result.error is None
