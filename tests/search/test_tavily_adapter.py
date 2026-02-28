# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for Tavily search adapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from flydesk.search.adapters.tavily import TavilyAdapter
from flydesk.search.provider import SearchProviderFactory, SearchResult


@pytest.fixture
def adapter():
    return TavilyAdapter(api_key="tvly-test-key")


@pytest.mark.asyncio
async def test_search_returns_results(adapter):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {
                "title": "Python Docs",
                "url": "https://docs.python.org",
                "content": "Official Python documentation",
                "score": 0.95,
                "published_date": "2026-01-01",
            },
            {
                "title": "Real Python",
                "url": "https://realpython.com",
                "content": "Python tutorials and articles",
                "score": 0.85,
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
    assert results[0].score == 0.95


@pytest.mark.asyncio
async def test_search_with_content_includes_raw(adapter):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {
                "title": "Example",
                "url": "https://example.com",
                "content": "Short snippet",
                "raw_content": "Full page content here with lots of text...",
                "score": 0.9,
            }
        ]
    }
    mock_response.raise_for_status.return_value = None

    with patch.object(adapter, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)
        results = await adapter.search_with_content("example query")

    assert len(results) == 1
    assert results[0].content == "Full page content here with lots of text..."


@pytest.mark.asyncio
async def test_search_handles_api_error(adapter):
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.raise_for_status.side_effect = Exception("Unauthorized")

    with patch.object(adapter, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)
        results = await adapter.search("test query")

    assert results == []


def test_tavily_registered_in_factory():
    assert "tavily" in SearchProviderFactory.available_providers()


def test_default_api_url():
    adapter = TavilyAdapter(api_key="tvly-test-key")
    assert adapter._api_url == "https://api.tavily.com"


def test_custom_api_url():
    adapter = TavilyAdapter(api_key="tvly-test-key", api_url="https://tavily.proxy.internal/")
    assert adapter._api_url == "https://tavily.proxy.internal"


@pytest.mark.asyncio
async def test_search_uses_configured_api_url():
    adapter = TavilyAdapter(api_key="tvly-test-key", api_url="https://custom.tavily.test")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"results": []}
    mock_response.raise_for_status.return_value = None

    with patch.object(adapter, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)
        await adapter.search("test query")

    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "https://custom.tavily.test/search"


@pytest.mark.asyncio
async def test_aclose(adapter):
    await adapter.aclose()
