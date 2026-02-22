# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for ConversationRepository."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.conversation.models import Conversation, Message, MessageRole
from flydesk.conversation.repository import ConversationRepository
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
    return ConversationRepository(session_factory)


@pytest.fixture
def sample_conversation() -> Conversation:
    return Conversation(
        id="conv-1",
        title="Test Conversation",
        user_id="user-1",
        model_id="gpt-4",
        metadata={"source": "test"},
    )


@pytest.fixture
def sample_message() -> Message:
    return Message(
        id="msg-1",
        conversation_id="conv-1",
        role=MessageRole.USER,
        content="Hello, world!",
    )


class TestConversationRepository:
    async def test_create_and_get_conversation(self, repo, sample_conversation):
        await repo.create_conversation(sample_conversation)
        result = await repo.get_conversation("conv-1", "user-1")
        assert result is not None
        assert result.title == "Test Conversation"
        assert result.user_id == "user-1"
        assert result.model_id == "gpt-4"
        assert result.status == "active"

    async def test_list_conversations_for_user(self, repo, sample_conversation):
        await repo.create_conversation(sample_conversation)

        conv2 = Conversation(
            id="conv-2",
            title="Second Conversation",
            user_id="user-1",
        )
        await repo.create_conversation(conv2)

        results = await repo.list_conversations("user-1")
        assert len(results) == 2

    async def test_update_conversation_title(self, repo, sample_conversation):
        await repo.create_conversation(sample_conversation)
        sample_conversation.title = "Updated Title"
        await repo.update_conversation(sample_conversation, "user-1")
        result = await repo.get_conversation("conv-1", "user-1")
        assert result is not None
        assert result.title == "Updated Title"

    async def test_delete_conversation_soft_deletes(self, repo, sample_conversation):
        await repo.create_conversation(sample_conversation)
        await repo.delete_conversation("conv-1", "user-1")
        # Conversation still exists with status "deleted"
        result = await repo.get_conversation("conv-1", "user-1")
        assert result is not None
        assert result.status == "deleted"

    async def test_add_and_get_messages(self, repo, sample_conversation, sample_message):
        await repo.create_conversation(sample_conversation)
        await repo.add_message(sample_message, "user-1")

        assistant_msg = Message(
            id="msg-2",
            conversation_id="conv-1",
            role=MessageRole.ASSISTANT,
            content="Hello! How can I help?",
        )
        await repo.add_message(assistant_msg, "user-1")

        messages = await repo.get_messages("conv-1", "user-1")
        assert len(messages) == 2
        assert messages[0].role == MessageRole.USER
        assert messages[0].content == "Hello, world!"
        assert messages[1].role == MessageRole.ASSISTANT
        assert messages[1].content == "Hello! How can I help?"

    async def test_list_conversations_excludes_deleted(self, repo, sample_conversation):
        await repo.create_conversation(sample_conversation)
        conv2 = Conversation(
            id="conv-2",
            title="Deleted Conversation",
            user_id="user-1",
        )
        await repo.create_conversation(conv2)
        await repo.delete_conversation("conv-2", "user-1")

        results = await repo.list_conversations("user-1")
        assert len(results) == 1
        assert results[0].id == "conv-1"

    async def test_get_conversation_not_found(self, repo):
        result = await repo.get_conversation("nonexistent", "user-1")
        assert result is None

    async def test_get_conversation_includes_message_count(
        self, repo, sample_conversation, sample_message
    ):
        await repo.create_conversation(sample_conversation)
        await repo.add_message(sample_message, "user-1")

        result = await repo.get_conversation("conv-1", "user-1")
        assert result is not None
        assert result.message_count == 1

    async def test_list_conversations_different_user(self, repo, sample_conversation):
        await repo.create_conversation(sample_conversation)
        results = await repo.list_conversations("user-2")
        assert len(results) == 0

    # -- Ownership denial tests --

    async def test_get_conversation_wrong_user_returns_none(
        self, repo, sample_conversation
    ):
        """A user who does not own the conversation gets None."""
        await repo.create_conversation(sample_conversation)
        result = await repo.get_conversation("conv-1", "user-other")
        assert result is None

    async def test_get_messages_wrong_user_returns_empty(
        self, repo, sample_conversation, sample_message
    ):
        """A user who does not own the conversation gets an empty list."""
        await repo.create_conversation(sample_conversation)
        await repo.add_message(sample_message, "user-1")

        messages = await repo.get_messages("conv-1", "user-other")
        assert messages == []

    async def test_update_conversation_wrong_user_raises(
        self, repo, sample_conversation
    ):
        """Updating a conversation you don't own raises ValueError."""
        await repo.create_conversation(sample_conversation)
        sample_conversation.title = "Hijacked"
        with pytest.raises(ValueError, match="not found"):
            await repo.update_conversation(sample_conversation, "user-other")

        # Verify it was NOT updated
        result = await repo.get_conversation("conv-1", "user-1")
        assert result is not None
        assert result.title == "Test Conversation"

    async def test_delete_conversation_wrong_user_no_effect(
        self, repo, sample_conversation
    ):
        """Deleting a conversation you don't own has no effect."""
        await repo.create_conversation(sample_conversation)
        await repo.delete_conversation("conv-1", "user-other")

        # Should still be active for the real owner
        result = await repo.get_conversation("conv-1", "user-1")
        assert result is not None
        assert result.status == "active"

    async def test_add_message_wrong_user_raises(
        self, repo, sample_conversation, sample_message
    ):
        """Adding a message to a conversation you don't own raises ValueError."""
        await repo.create_conversation(sample_conversation)
        with pytest.raises(ValueError, match="not found"):
            await repo.add_message(sample_message, "user-other")

        # Verify no message was added
        messages = await repo.get_messages("conv-1", "user-1")
        assert messages == []
