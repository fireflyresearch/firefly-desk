# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for EmailThreadTracker."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.models.base import Base
from flydesk.email.threading import EmailThreadTracker


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def tracker(session_factory):
    return EmailThreadTracker(session_factory)


class TestEmailThreadTracker:
    async def test_new_thread_creates_conversation(self, tracker):
        conv_id, is_new = await tracker.resolve_conversation(
            message_id="<msg-1@example.com>",
            in_reply_to=None,
            references=[],
            subject="Hello",
        )
        assert is_new is True
        assert conv_id  # non-empty string

    async def test_reply_finds_existing_conversation(self, tracker):
        # First message creates thread
        conv_id_1, _ = await tracker.resolve_conversation(
            message_id="<msg-1@example.com>",
            in_reply_to=None,
            references=[],
            subject="Hello",
        )
        # Reply finds it
        conv_id_2, is_new = await tracker.resolve_conversation(
            message_id="<msg-2@example.com>",
            in_reply_to="<msg-1@example.com>",
            references=["<msg-1@example.com>"],
            subject="Re: Hello",
        )
        assert is_new is False
        assert conv_id_2 == conv_id_1

    async def test_references_fallback(self, tracker):
        conv_id_1, _ = await tracker.resolve_conversation(
            message_id="<msg-1@example.com>",
            in_reply_to=None,
            references=[],
            subject="Test",
        )
        # No in_reply_to but references include the original
        conv_id_2, is_new = await tracker.resolve_conversation(
            message_id="<msg-3@example.com>",
            in_reply_to=None,
            references=["<msg-1@example.com>"],
            subject="Re: Test",
        )
        assert is_new is False
        assert conv_id_2 == conv_id_1

    async def test_unrelated_message_creates_new_conversation(self, tracker):
        conv_id_1, is_new_1 = await tracker.resolve_conversation(
            message_id="<msg-1@example.com>",
            in_reply_to=None,
            references=[],
            subject="Thread A",
        )
        conv_id_2, is_new_2 = await tracker.resolve_conversation(
            message_id="<msg-2@example.com>",
            in_reply_to=None,
            references=[],
            subject="Thread B",
        )
        assert is_new_1 is True
        assert is_new_2 is True
        assert conv_id_1 != conv_id_2

    async def test_deep_thread_chain(self, tracker):
        """A chain of replies all resolve to the same conversation."""
        conv_id_1, _ = await tracker.resolve_conversation(
            message_id="<msg-1@example.com>",
            in_reply_to=None,
            references=[],
            subject="Start",
        )
        conv_id_2, is_new_2 = await tracker.resolve_conversation(
            message_id="<msg-2@example.com>",
            in_reply_to="<msg-1@example.com>",
            references=["<msg-1@example.com>"],
            subject="Re: Start",
        )
        conv_id_3, is_new_3 = await tracker.resolve_conversation(
            message_id="<msg-3@example.com>",
            in_reply_to="<msg-2@example.com>",
            references=["<msg-1@example.com>", "<msg-2@example.com>"],
            subject="Re: Re: Start",
        )
        assert is_new_2 is False
        assert is_new_3 is False
        assert conv_id_1 == conv_id_2 == conv_id_3

    async def test_participants_stored(self, tracker, session_factory):
        """Participants are persisted in the email_threads row."""
        from flydesk.models.email_thread import EmailThreadRow
        from sqlalchemy import select
        import json

        participants = [
            {"email": "alice@example.com", "name": "Alice"},
            {"email": "bob@example.com", "name": "Bob"},
        ]
        conv_id, _ = await tracker.resolve_conversation(
            message_id="<msg-p@example.com>",
            in_reply_to=None,
            references=[],
            subject="With participants",
            participants=participants,
        )

        async with session_factory() as session:
            stmt = select(EmailThreadRow).where(
                EmailThreadRow.email_message_id == "<msg-p@example.com>"
            )
            result = await session.execute(stmt)
            row = result.scalar_one()
            assert row.conversation_id == conv_id
            assert row.subject == "With participants"
            stored = json.loads(row.participants_json)
            assert len(stored) == 2
            assert stored[0]["email"] == "alice@example.com"
