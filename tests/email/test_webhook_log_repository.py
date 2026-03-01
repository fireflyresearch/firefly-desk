# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for WebhookLogRepository -- CRUD for inbound webhook log entries."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.email.webhook_log import WebhookLogEntry
from flydesk.email.webhook_log_repository import WebhookLogRepository
from flydesk.models.base import Base


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def repo(session_factory):
    return WebhookLogRepository(session_factory)


def _make_entry(
    entry_id: str = "e-1",
    provider: str = "sendgrid",
    status: str = "received",
    **kwargs,
) -> WebhookLogEntry:
    now = kwargs.pop("timestamp", datetime.now(timezone.utc))
    return WebhookLogEntry(
        id=entry_id,
        timestamp=now,
        provider=provider,
        status=status,
        from_address=kwargs.pop("from_address", "alice@example.com"),
        subject=kwargs.pop("subject", "Hello"),
        payload_preview=kwargs.pop("payload_preview", '{"key": "value"}'),
        processing_time_ms=kwargs.pop("processing_time_ms", 12.5),
        error=kwargs.pop("error", None),
    )


class TestRecord:
    async def test_persists_and_retrieves(self, repo):
        """record() persists the entry and returns its ID; get() retrieves it."""
        entry = _make_entry()
        returned_id = await repo.record(entry)
        assert returned_id == "e-1"

        result = await repo.get("e-1")
        assert result is not None
        assert result.id == "e-1"
        assert result.provider == "sendgrid"
        assert result.status == "received"
        assert result.from_address == "alice@example.com"
        assert result.subject == "Hello"
        assert result.payload_preview == '{"key": "value"}'
        assert result.processing_time_ms == 12.5
        assert result.error is None

    async def test_persists_entry_with_error(self, repo):
        """record() stores error text correctly."""
        entry = _make_entry(error="Connection refused")
        await repo.record(entry)

        result = await repo.get("e-1")
        assert result is not None
        assert result.error == "Connection refused"


class TestList:
    async def test_newest_first(self, repo):
        """list() returns entries ordered by created_at descending."""
        now = datetime.now(timezone.utc)
        await repo.record(_make_entry("e-1", timestamp=now - timedelta(minutes=3)))
        await repo.record(_make_entry("e-2", timestamp=now - timedelta(minutes=2)))
        await repo.record(_make_entry("e-3", timestamp=now - timedelta(minutes=1)))

        result = await repo.list()
        assert len(result) == 3
        assert result[0].id == "e-3"
        assert result[1].id == "e-2"
        assert result[2].id == "e-1"

    async def test_filter_by_status(self, repo):
        """list() filters by status when provided."""
        await repo.record(_make_entry("e-1", status="received"))
        await repo.record(_make_entry("e-2", status="processed"))
        await repo.record(_make_entry("e-3", status="error"))

        result = await repo.list(status="error")
        assert len(result) == 1
        assert result[0].id == "e-3"

    async def test_filter_by_provider(self, repo):
        """list() filters by provider when provided."""
        await repo.record(_make_entry("e-1", provider="sendgrid"))
        await repo.record(_make_entry("e-2", provider="ses"))
        await repo.record(_make_entry("e-3", provider="sendgrid"))

        result = await repo.list(provider="ses")
        assert len(result) == 1
        assert result[0].id == "e-2"

    async def test_pagination(self, repo):
        """list() respects limit and offset."""
        now = datetime.now(timezone.utc)
        for i in range(5):
            await repo.record(
                _make_entry(f"e-{i}", timestamp=now + timedelta(seconds=i))
            )

        result = await repo.list(limit=2, offset=1)
        assert len(result) == 2
        # Newest first: e-4, e-3, e-2, e-1, e-0
        # offset=1 skips e-4, limit=2 returns e-3, e-2
        assert result[0].id == "e-3"
        assert result[1].id == "e-2"


class TestClear:
    async def test_deletes_all(self, repo):
        """clear() removes all entries and returns the count."""
        await repo.record(_make_entry("e-1"))
        await repo.record(_make_entry("e-2"))
        await repo.record(_make_entry("e-3"))

        deleted = await repo.clear()
        assert deleted == 3

        remaining = await repo.list()
        assert remaining == []

    async def test_clear_empty(self, repo):
        """clear() on an empty table returns 0."""
        deleted = await repo.clear()
        assert deleted == 0


class TestGet:
    async def test_returns_none_for_missing(self, repo):
        """get() returns None when the entry does not exist."""
        result = await repo.get("nonexistent")
        assert result is None


class TestCleanup:
    async def test_deletes_old_entries(self, repo):
        """cleanup() deletes entries older than the threshold."""
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=60)

        await repo.record(_make_entry("e-old", timestamp=old))
        await repo.record(_make_entry("e-new", timestamp=now))

        deleted = await repo.cleanup(older_than_days=30)
        assert deleted == 1

        remaining = await repo.list()
        assert len(remaining) == 1
        assert remaining[0].id == "e-new"
