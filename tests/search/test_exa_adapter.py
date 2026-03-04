# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for Exa AI search adapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from flydesk.search.adapters.exa import ExaAdapter
from flydesk.search.provider import SearchProviderFactory, SearchResult


@pytest.fixture
def adapter():
    return ExaAdapter(api_key="exa-test-key")


@pytest.mark.asyncio
async def test_search_returns_results(adapter):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {
                "title": "Python Docs",
                "url": "https://docs.python.org",
                "highlights": ["Official Python documentation", "Python 3 reference"],
                "publishedDate": "2026-01-01",
            },
            {
                "title": "Real Python",
                "url": "https://realpython.com",
                "highlights": ["Python tutorials and articles"],
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
    assert results[0].snippet == "Official Python documentation Python 3 reference"
    assert results[0].published_date == "2026-01-01"
    assert results[0].content is None
    assert results[0].score is None


@pytest.mark.asyncio
async def test_search_with_content_includes_text(adapter):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {
                "title": "Example",
                "url": "https://example.com",
                "highlights": ["Short snippet"],
                "text": "Full page content here with lots of text...",
            }
        ]
    }
    mock_response.raise_for_status.return_value = None

    with patch.object(adapter, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)
        results = await adapter.search_with_content("example query")

    assert len(results) == 1
    assert results[0].content == "Full page content here with lots of text..."
    assert results[0].snippet == "Short snippet"

    # Verify text: true was included in the contents payload
    call_args = mock_client.post.call_args
    payload = call_args[1]["json"]
    assert payload["contents"]["text"] is True
    assert payload["contents"]["highlights"] is True


@pytest.mark.asyncio
async def test_search_without_content_omits_text_flag(adapter):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"results": []}
    mock_response.raise_for_status.return_value = None

    with patch.object(adapter, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)
        await adapter.search("test query")

    call_args = mock_client.post.call_args
    payload = call_args[1]["json"]
    assert "text" not in payload["contents"]
    assert payload["contents"]["highlights"] is True


@pytest.mark.asyncio
async def test_search_handles_api_error(adapter):
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.raise_for_status.side_effect = Exception("Unauthorized")

    with patch.object(adapter, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)
        results = await adapter.search("test query")

    assert results == []


def test_exa_registered_in_factory():
    assert "exa" in SearchProviderFactory.available_providers()


def test_default_api_url():
    adapter = ExaAdapter(api_key="exa-test-key")
    assert adapter._api_url == "https://api.exa.ai"


def test_custom_api_url():
    adapter = ExaAdapter(api_key="exa-test-key", api_url="https://exa.proxy.internal/")
    assert adapter._api_url == "https://exa.proxy.internal"


def test_api_key_header():
    adapter = ExaAdapter(api_key="exa-secret-key")
    assert adapter._client.headers["x-api-key"] == "exa-secret-key"


@pytest.mark.asyncio
async def test_search_falls_back_to_title_when_no_highlights(adapter):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {
                "title": "Fallback Title",
                "url": "https://example.com",
            }
        ]
    }
    mock_response.raise_for_status.return_value = None

    with patch.object(adapter, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)
        results = await adapter.search("test")

    assert results[0].snippet == "Fallback Title"


@pytest.mark.asyncio
async def test_aclose(adapter):
    await adapter.aclose()
