# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for Nimbleway search adapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from flydesk.search.adapters.nimbleway import NimblewayAdapter
from flydesk.search.provider import SearchProviderFactory, SearchResult


@pytest.fixture
def adapter():
    return NimblewayAdapter(api_key="nimble-test-key")


@pytest.mark.asyncio
async def test_search_returns_results(adapter):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {
                "title": "Python Docs",
                "url": "https://docs.python.org",
                "description": "Official Python documentation",
            },
            {
                "title": "Real Python",
                "url": "https://realpython.com",
                "description": "Python tutorials and articles",
            },
        ]
    }
    mock_response.raise_for_status.return_value = None

    with patch.object(adapter, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)
        results = await adapter.search("python tutorials", max_results=2)

    assert len(results) == 2
    assert results[0].title == "Python Docs"
    assert results[0].url == "https://docs.python.org"
    assert results[0].snippet == "Official Python documentation"
    assert results[0].score is None
    assert results[0].content is None


@pytest.mark.asyncio
async def test_search_with_content_includes_parsed(adapter):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {
                "title": "Example",
                "url": "https://example.com",
                "description": "Short snippet",
                "content": "# Full Markdown Content\n\nParsed page text...",
            }
        ]
    }
    mock_response.raise_for_status.return_value = None

    with patch.object(adapter, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)
        results = await adapter.search_with_content("example query")

    assert len(results) == 1
    assert results[0].content == "# Full Markdown Content\n\nParsed page text..."
    assert results[0].snippet == "Short snippet"

    # Verify parsing_type was included in the request payload
    call_args = mock_client.post.call_args
    payload = call_args[1]["json"]
    assert payload["parsing_type"] == "markdown"


@pytest.mark.asyncio
async def test_search_handles_api_error(adapter):
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.raise_for_status.side_effect = Exception("Unauthorized")

    with patch.object(adapter, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)
        results = await adapter.search("test query")

    assert results == []


def test_nimbleway_registered_in_factory():
    assert "nimbleway" in SearchProviderFactory.available_providers()


def test_default_api_url():
    adapter = NimblewayAdapter(api_key="nimble-test-key")
    assert adapter._api_url == "https://nimble-retriever.webit.live"


def test_custom_api_url():
    adapter = NimblewayAdapter(api_key="nimble-test-key", api_url="https://nimble.proxy.internal/")
    assert adapter._api_url == "https://nimble.proxy.internal"


def test_bearer_auth_header():
    adapter = NimblewayAdapter(api_key="nimble-secret-key")
    assert adapter._client.headers["authorization"] == "Bearer nimble-secret-key"


@pytest.mark.asyncio
async def test_aclose(adapter):
    await adapter.aclose()
