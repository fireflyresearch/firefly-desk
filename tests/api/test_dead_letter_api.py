"""Tests for DLQ admin API endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_request():
    request = MagicMock()
    request.app.state.dead_letter = AsyncMock()
    return request


@pytest.mark.asyncio
async def test_list_entries_empty(mock_request):
    from flydesk.api.dead_letter import list_entries

    mock_request.app.state.dead_letter.list_entries.return_value = []
    result = await list_entries(mock_request)
    assert result == {"entries": [], "total": 0}


@pytest.mark.asyncio
async def test_list_entries_with_data(mock_request):
    from flydesk.api.dead_letter import list_entries
    from datetime import datetime, timezone

    entry = MagicMock()
    entry.id = "e1"
    entry.source_type = "job"
    entry.source_id = "j1"
    entry.error = "timeout"
    entry.attempts = 2
    entry.max_attempts = 3
    entry.created_at = datetime(2026, 3, 5, tzinfo=timezone.utc)
    mock_request.app.state.dead_letter.list_entries.return_value = [entry]

    result = await list_entries(mock_request)
    assert result["total"] == 1
    assert result["entries"][0]["id"] == "e1"


@pytest.mark.asyncio
async def test_retry_entry_found(mock_request):
    from flydesk.api.dead_letter import retry_entry

    entry = MagicMock()
    entry.id = "e1"
    entry.attempts = 3
    mock_request.app.state.dead_letter.retry.return_value = entry

    result = await retry_entry(mock_request, entry_id="e1")
    assert result["id"] == "e1"
    assert result["status"] == "retrying"


@pytest.mark.asyncio
async def test_retry_entry_not_found(mock_request):
    from flydesk.api.dead_letter import retry_entry

    mock_request.app.state.dead_letter.retry.return_value = None
    result = await retry_entry(mock_request, entry_id="nonexistent")
    assert result.status_code == 404


@pytest.mark.asyncio
async def test_delete_entry_found(mock_request):
    from flydesk.api.dead_letter import delete_entry

    mock_request.app.state.dead_letter.remove.return_value = True
    result = await delete_entry(mock_request, entry_id="e1")
    assert result["status"] == "deleted"


@pytest.mark.asyncio
async def test_delete_entry_not_found(mock_request):
    from flydesk.api.dead_letter import delete_entry

    mock_request.app.state.dead_letter.remove.return_value = False
    result = await delete_entry(mock_request, entry_id="nonexistent")
    assert result.status_code == 404
