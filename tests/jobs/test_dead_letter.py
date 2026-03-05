# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for dead-letter queue repository."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    # session.add() is synchronous in AsyncSession, so use a plain MagicMock
    session.add = MagicMock()
    return session


@pytest.fixture
def repo(mock_session):
    from flydesk.jobs.dead_letter import DeadLetterRepository

    factory = MagicMock(return_value=mock_session)
    return DeadLetterRepository(factory)


@pytest.mark.asyncio
async def test_add_creates_entry(repo, mock_session):
    entry_id = await repo.add("job", "job-123", {"type": "indexing"}, "Connection refused")
    assert isinstance(entry_id, str)
    assert len(entry_id) > 0
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_list_entries_empty(repo, mock_session):
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    entries = await repo.list_entries()
    assert entries == []


@pytest.mark.asyncio
async def test_list_entries_with_filter(repo, mock_session):
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    entries = await repo.list_entries(source_type="job")
    assert entries == []
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_retry_increments_attempts(repo, mock_session):
    mock_entry = MagicMock()
    mock_entry.attempts = 1
    mock_session.get.return_value = mock_entry

    result = await repo.retry("entry-1")
    assert result is not None
    assert mock_entry.attempts == 2
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_retry_returns_none_for_missing(repo, mock_session):
    mock_session.get.return_value = None
    result = await repo.retry("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_remove_returns_true(repo, mock_session):
    mock_result = MagicMock()
    type(mock_result).rowcount = PropertyMock(return_value=1)
    mock_session.execute.return_value = mock_result

    removed = await repo.remove("entry-1")
    assert removed is True


@pytest.mark.asyncio
async def test_remove_returns_false_for_missing(repo, mock_session):
    mock_result = MagicMock()
    type(mock_result).rowcount = PropertyMock(return_value=0)
    mock_session.execute.return_value = mock_result

    removed = await repo.remove("nonexistent")
    assert removed is False
