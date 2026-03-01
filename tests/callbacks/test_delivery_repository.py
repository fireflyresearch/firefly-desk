# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for CallbackDeliveryRepository -- delivery log persistence."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.callbacks.delivery_repository import CallbackDeliveryRepository
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
    return CallbackDeliveryRepository(session_factory)


class TestRecord:
    async def test_persists_delivery(self, repo):
        """record() persists a successful delivery and returns its ID."""
        row_id = await repo.record(
            callback_id="cb-1",
            event="email.sent",
            url="https://example.com/hook",
            attempt=1,
            status="success",
            status_code=200,
            payload={"message_id": "msg-1"},
        )
        assert row_id is not None

        entries = await repo.list()
        assert len(entries) == 1
        entry = entries[0]
        assert entry["id"] == row_id
        assert entry["callback_id"] == "cb-1"
        assert entry["event"] == "email.sent"
        assert entry["url"] == "https://example.com/hook"
        assert entry["attempt"] == 1
        assert entry["status"] == "success"
        assert entry["status_code"] == 200
        assert entry["payload"] == {"message_id": "msg-1"}
        assert entry["created_at"] is not None

    async def test_records_failure_with_error(self, repo):
        """record() persists a failed delivery with error details."""
        row_id = await repo.record(
            callback_id="cb-2",
            event="email.failed",
            url="https://example.com/hook",
            attempt=3,
            status="failed",
            status_code=500,
            error="Internal Server Error",
        )
        assert row_id is not None

        entries = await repo.list()
        assert len(entries) == 1
        entry = entries[0]
        assert entry["status"] == "failed"
        assert entry["status_code"] == 500
        assert entry["error"] == "Internal Server Error"
        assert entry["attempt"] == 3
        assert entry["payload"] is None


class TestList:
    async def test_filter_by_callback_id(self, repo):
        """list() filters entries by callback_id."""
        await repo.record(callback_id="cb-1", event="email.sent", url="https://a.com", status="success")
        await repo.record(callback_id="cb-2", event="email.sent", url="https://b.com", status="success")
        await repo.record(callback_id="cb-1", event="email.failed", url="https://a.com", status="failed")

        entries = await repo.list(callback_id="cb-1")
        assert len(entries) == 2
        assert all(e["callback_id"] == "cb-1" for e in entries)

    async def test_filter_by_event(self, repo):
        """list() filters entries by event type."""
        await repo.record(callback_id="cb-1", event="email.sent", url="https://a.com", status="success")
        await repo.record(callback_id="cb-1", event="email.received", url="https://a.com", status="success")
        await repo.record(callback_id="cb-2", event="email.sent", url="https://b.com", status="success")

        entries = await repo.list(event="email.sent")
        assert len(entries) == 2
        assert all(e["event"] == "email.sent" for e in entries)

    async def test_filter_by_status(self, repo):
        """list() filters entries by status."""
        await repo.record(callback_id="cb-1", event="email.sent", url="https://a.com", status="success")
        await repo.record(callback_id="cb-1", event="email.sent", url="https://a.com", status="failed", error="timeout")
        await repo.record(callback_id="cb-2", event="email.sent", url="https://b.com", status="pending")

        entries = await repo.list(status="failed")
        assert len(entries) == 1
        assert entries[0]["status"] == "failed"

    async def test_list_respects_limit_and_offset(self, repo):
        """list() respects limit and offset parameters."""
        for i in range(5):
            await repo.record(
                callback_id=f"cb-{i}",
                event="email.sent",
                url="https://a.com",
                status="success",
            )

        entries = await repo.list(limit=2, offset=1)
        assert len(entries) == 2

    async def test_list_returns_newest_first(self, repo):
        """list() returns entries ordered by created_at descending."""
        id1 = await repo.record(callback_id="cb-1", event="email.sent", url="https://a.com", status="success")
        id2 = await repo.record(callback_id="cb-2", event="email.sent", url="https://a.com", status="success")

        entries = await repo.list()
        assert len(entries) == 2
        # Most recently inserted should be first
        assert entries[0]["id"] == id2
        assert entries[1]["id"] == id1


class TestClear:
    async def test_removes_all(self, repo):
        """clear() removes all delivery log entries."""
        await repo.record(callback_id="cb-1", event="email.sent", url="https://a.com", status="success")
        await repo.record(callback_id="cb-2", event="email.sent", url="https://b.com", status="failed")

        deleted = await repo.clear()
        assert deleted == 2

        entries = await repo.list()
        assert len(entries) == 0

    async def test_clear_empty_table(self, repo):
        """clear() on an empty table returns 0."""
        deleted = await repo.clear()
        assert deleted == 0
