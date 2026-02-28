# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Map email threads to Firefly Desk conversations."""

from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.models.email_thread import EmailThreadRow

logger = logging.getLogger(__name__)


class EmailThreadTracker:
    """Resolves email threads to conversation IDs."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def resolve_conversation(
        self,
        message_id: str,
        in_reply_to: str | None,
        references: list[str],
        subject: str,
        participants: list[dict] | None = None,
    ) -> tuple[str, bool]:
        """Resolve an email to a conversation ID.

        Returns (conversation_id, is_new) -- True if a new conversation was created.
        """
        # 1. Check In-Reply-To header
        if in_reply_to:
            thread = await self._find_by_message_id(in_reply_to)
            if thread is not None:
                await self._record_message(
                    thread.conversation_id, message_id, thread.thread_root_id, subject, participants,
                )
                return thread.conversation_id, False

        # 2. Check References headers
        for ref in references:
            thread = await self._find_by_message_id(ref)
            if thread is not None:
                await self._record_message(
                    thread.conversation_id, message_id, thread.thread_root_id, subject, participants,
                )
                return thread.conversation_id, False

        # 3. New thread -- create conversation
        conversation_id = str(uuid.uuid4())
        await self._record_message(conversation_id, message_id, message_id, subject, participants)
        return conversation_id, True

    async def _find_by_message_id(self, message_id: str) -> EmailThreadRow | None:
        async with self._session_factory() as session:
            stmt = select(EmailThreadRow).where(EmailThreadRow.email_message_id == message_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def _record_message(
        self,
        conversation_id: str,
        message_id: str,
        thread_root_id: str | None,
        subject: str,
        participants: list[dict] | None,
    ) -> None:
        async with self._session_factory() as session:
            row = EmailThreadRow(
                id=str(uuid.uuid4()),
                conversation_id=conversation_id,
                email_message_id=message_id,
                thread_root_id=thread_root_id,
                subject=subject,
                participants_json=json.dumps(participants) if participants else None,
            )
            session.add(row)
            await session.commit()
