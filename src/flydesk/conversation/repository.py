# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Persistence layer for Conversations and Messages."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.conversation.models import Conversation, Message, MessageRole
from flydesk.models.conversation import ConversationRow, MessageRow


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
                created_at=conversation.created_at,
                updated_at=conversation.updated_at,
            )
            session.add(row)
            await session.commit()

    async def get_conversation(
        self, conversation_id: str, user_id: str, *, include_deleted: bool = False
    ) -> Conversation | None:
        """Retrieve a conversation by ID and owner, or ``None`` if not found/owned."""
        async with self._session_factory() as session:
            stmt = select(ConversationRow).where(
                ConversationRow.id == conversation_id,
                ConversationRow.user_id == user_id,
            )
            if not include_deleted:
                stmt = stmt.where(ConversationRow.status != "deleted")
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
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

    async def update_conversation(
        self, conversation: Conversation, user_id: str
    ) -> None:
        """Update an existing conversation after verifying ownership."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(ConversationRow).where(
                    ConversationRow.id == conversation.id,
                    ConversationRow.user_id == user_id,
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                msg = f"Conversation {conversation.id} not found"
                raise ValueError(msg)
            row.title = conversation.title
            row.model_id = conversation.model_id
            row.metadata_ = _to_json(conversation.metadata)
            row.status = conversation.status
            await session.commit()

    async def conversation_exists(self, conversation_id: str) -> bool:
        """Check whether a conversation row exists (any owner).

        This is safe because it only returns a boolean, never the
        conversation data itself, so no information is leaked.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(ConversationRow.id).where(
                    ConversationRow.id == conversation_id,
                )
            )
            return result.scalar_one_or_none() is not None

    async def delete_conversation(
        self, conversation_id: str, user_id: str
    ) -> None:
        """Soft-delete a conversation by setting status to 'deleted', only if owned."""
        async with self._session_factory() as session:
            await session.execute(
                update(ConversationRow)
                .where(
                    ConversationRow.id == conversation_id,
                    ConversationRow.user_id == user_id,
                )
                .values(status="deleted", deleted_at=datetime.now(timezone.utc))
            )
            await session.commit()

    # -- Messages --

    async def add_message(self, message: Message, user_id: str) -> None:
        """Persist a new message after verifying conversation ownership."""
        async with self._session_factory() as session:
            # Verify the caller owns the conversation
            owner_check = await session.execute(
                select(ConversationRow.id).where(
                    ConversationRow.id == message.conversation_id,
                    ConversationRow.user_id == user_id,
                )
            )
            if owner_check.scalar_one_or_none() is None:
                msg = f"Conversation {message.conversation_id} not found"
                raise ValueError(msg)

            status_check = await session.execute(
                select(ConversationRow.status).where(
                    ConversationRow.id == message.conversation_id
                )
            )
            if status_check.scalar_one_or_none() == "deleted":
                msg = f"Conversation {message.conversation_id} is deleted"
                raise ValueError(msg)

            metadata = dict(message.metadata)
            if message.file_ids:
                metadata["file_ids"] = message.file_ids
            row = MessageRow(
                id=message.id,
                conversation_id=message.conversation_id,
                role=message.role.value,
                content=message.content,
                metadata_=_to_json(metadata),
            )
            session.add(row)
            await session.commit()

    async def get_messages(
        self,
        conversation_id: str,
        user_id: str,
        *,
        limit: int = 100,
    ) -> list[Message]:
        """Return messages for a conversation, oldest first, only if owned."""
        async with self._session_factory() as session:
            # Verify the caller owns the conversation
            owner_check = await session.execute(
                select(ConversationRow.id).where(
                    ConversationRow.id == conversation_id,
                    ConversationRow.user_id == user_id,
                )
            )
            if owner_check.scalar_one_or_none() is None:
                return []

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
            deleted_at=row.deleted_at,
        )

    @staticmethod
    def _row_to_message(row: MessageRow) -> Message:
        metadata = _from_json(row.metadata_) if row.metadata_ else {}
        file_ids = metadata.pop("file_ids", []) if isinstance(metadata, dict) else []
        return Message(
            id=row.id,
            conversation_id=row.conversation_id,
            role=MessageRole(row.role),
            content=row.content,
            file_ids=file_ids,
            metadata=metadata,
            created_at=row.created_at,
        )
