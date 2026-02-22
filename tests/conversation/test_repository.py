# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for ConversationRepository."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydek.conversation.models import Conversation, Message, MessageRole
from flydek.conversation.repository import ConversationRepository
from flydek.models.base import Base


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
        result = await repo.get_conversation("conv-1")
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
        await repo.update_conversation(sample_conversation)
        result = await repo.get_conversation("conv-1")
        assert result is not None
        assert result.title == "Updated Title"

    async def test_delete_conversation_soft_deletes(self, repo, sample_conversation):
        await repo.create_conversation(sample_conversation)
        await repo.delete_conversation("conv-1")
        # Conversation still exists with status "deleted"
        result = await repo.get_conversation("conv-1")
        assert result is not None
        assert result.status == "deleted"

    async def test_add_and_get_messages(self, repo, sample_conversation, sample_message):
        await repo.create_conversation(sample_conversation)
        await repo.add_message(sample_message)

        assistant_msg = Message(
            id="msg-2",
            conversation_id="conv-1",
            role=MessageRole.ASSISTANT,
            content="Hello! How can I help?",
        )
        await repo.add_message(assistant_msg)

        messages = await repo.get_messages("conv-1")
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
        await repo.delete_conversation("conv-2")

        results = await repo.list_conversations("user-1")
        assert len(results) == 1
        assert results[0].id == "conv-1"

    async def test_get_conversation_not_found(self, repo):
        result = await repo.get_conversation("nonexistent")
        assert result is None

    async def test_get_conversation_includes_message_count(
        self, repo, sample_conversation, sample_message
    ):
        await repo.create_conversation(sample_conversation)
        await repo.add_message(sample_message)

        result = await repo.get_conversation("conv-1")
        assert result is not None
        assert result.message_count == 1

    async def test_list_conversations_different_user(self, repo, sample_conversation):
        await repo.create_conversation(sample_conversation)
        results = await repo.list_conversations("user-2")
        assert len(results) == 0
