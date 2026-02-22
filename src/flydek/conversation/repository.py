# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Persistence layer for Conversations and Messages."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydek.conversation.models import Conversation, Message, MessageRole
from flydek.models.conversation import ConversationRow, MessageRow


def _to_json(value: Any) -> str | None:
    """Serialize a Python object to a JSON string for SQLite Text columns."""
    if value is None:
        return None
    return json.dumps(value, default=str)


def _from_json(value: Any) -> dict | list:
    """Deserialize a value that may be a JSON string (SQLite) or already a dict/list."""
    if isinstance(value, str):
        return json.loads(value)
    return value


class ConversationRepository:
    """CRUD operations for conversations and messages."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    # -- Conversations --

    async def create_conversation(self, conversation: Conversation) -> None:
        """Persist a new conversation."""
        async with self._session_factory() as session:
            row = ConversationRow(
                id=conversation.id,
                title=conversation.title,
                user_id=conversation.user_id,
                model_id=conversation.model_id,
                metadata_=_to_json(conversation.metadata),
                status=conversation.status,
            )
            session.add(row)
            await session.commit()

    async def get_conversation(self, conversation_id: str) -> Conversation | None:
        """Retrieve a conversation by ID, or ``None`` if not found."""
        async with self._session_factory() as session:
            row = await session.get(ConversationRow, conversation_id)
            if row is None:
                return None
            # Count messages for this conversation
            count_result = await session.execute(
                select(func.count()).where(MessageRow.conversation_id == conversation_id)
            )
            message_count = count_result.scalar() or 0
            return self._row_to_conversation(row, message_count=message_count)

    async def list_conversations(
        self,
        user_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Conversation]:
        """Return conversations for a user, most recent first, excluding deleted."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(ConversationRow)
                .where(ConversationRow.user_id == user_id)
                .where(ConversationRow.status != "deleted")
                .order_by(ConversationRow.updated_at.desc())
                .limit(limit)
                .offset(offset)
            )
            return [self._row_to_conversation(r) for r in result.scalars().all()]

    async def update_conversation(self, conversation: Conversation) -> None:
        """Update an existing conversation."""
        async with self._session_factory() as session:
            row = await session.get(ConversationRow, conversation.id)
            if row is None:
                msg = f"Conversation {conversation.id} not found"
                raise ValueError(msg)
            row.title = conversation.title
            row.model_id = conversation.model_id
            row.metadata_ = _to_json(conversation.metadata)
            row.status = conversation.status
            await session.commit()

    async def delete_conversation(self, conversation_id: str) -> None:
        """Soft-delete a conversation by setting status to 'deleted'."""
        async with self._session_factory() as session:
            await session.execute(
                update(ConversationRow)
                .where(ConversationRow.id == conversation_id)
                .values(status="deleted")
            )
            await session.commit()

    # -- Messages --

    async def add_message(self, message: Message) -> None:
        """Persist a new message."""
        async with self._session_factory() as session:
            row = MessageRow(
                id=message.id,
                conversation_id=message.conversation_id,
                role=message.role.value,
                content=message.content,
                metadata_=_to_json(message.metadata),
            )
            session.add(row)
            await session.commit()

    async def get_messages(
        self,
        conversation_id: str,
        *,
        limit: int = 100,
    ) -> list[Message]:
        """Return messages for a conversation, oldest first."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(MessageRow)
                .where(MessageRow.conversation_id == conversation_id)
                .order_by(MessageRow.created_at.asc())
                .limit(limit)
            )
            return [self._row_to_message(r) for r in result.scalars().all()]

    # -- Mapping helpers --

    @staticmethod
    def _row_to_conversation(
        row: ConversationRow, *, message_count: int = 0
    ) -> Conversation:
        return Conversation(
            id=row.id,
            title=row.title,
            user_id=row.user_id,
            model_id=row.model_id,
            metadata=_from_json(row.metadata_) if row.metadata_ else {},
            status=row.status,
            message_count=message_count,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _row_to_message(row: MessageRow) -> Message:
        return Message(
            id=row.id,
            conversation_id=row.conversation_id,
            role=MessageRole(row.role),
            content=row.content,
            metadata=_from_json(row.metadata_) if row.metadata_ else {},
            created_at=row.created_at,
        )
