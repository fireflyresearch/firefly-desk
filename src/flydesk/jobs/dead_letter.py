# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Repository for the dead-letter queue."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.models.dead_letter import DeadLetterEntryRow

logger = logging.getLogger(__name__)


class DeadLetterRepository:
    """CRUD operations for dead-letter queue entries."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add(
        self,
        source_type: str,
        source_id: str | None,
        payload: Any,
        error: str | None = None,
        *,
        max_attempts: int = 3,
    ) -> str:
        """Create a new dead-letter entry and return its ID."""
        entry_id = str(uuid4())
        now = datetime.now(timezone.utc)
        async with self._session_factory() as session:
            row = DeadLetterEntryRow(
                id=entry_id,
                source_type=source_type,
                source_id=source_id,
                payload_json=json.dumps(payload, default=str),
                error=error,
                attempts=0,
                max_attempts=max_attempts,
                created_at=now,
                updated_at=None,
            )
            session.add(row)
            await session.commit()
        return entry_id

    async def list_entries(
        self,
        source_type: str | None = None,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DeadLetterEntryRow]:
        """Return dead-letter entries, optionally filtered by source_type."""
        async with self._session_factory() as session:
            stmt = select(DeadLetterEntryRow)
            if source_type is not None:
                stmt = stmt.where(DeadLetterEntryRow.source_type == source_type)
            stmt = (
                stmt.order_by(DeadLetterEntryRow.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def retry(self, entry_id: str) -> DeadLetterEntryRow | None:
        """Increment the attempt counter and update the timestamp.

        Returns the updated row, or ``None`` if the entry does not exist.
        """
        async with self._session_factory() as session:
            row = await session.get(DeadLetterEntryRow, entry_id)
            if row is None:
                return None
            row.attempts += 1
            row.updated_at = datetime.now(timezone.utc)
            await session.commit()
            return row

    async def remove(self, entry_id: str) -> bool:
        """Delete a dead-letter entry. Returns ``True`` if it existed."""
        async with self._session_factory() as session:
            result = await session.execute(
                delete(DeadLetterEntryRow).where(DeadLetterEntryRow.id == entry_id)
            )
            await session.commit()
            return (result.rowcount or 0) > 0

    async def cleanup(self, older_than_days: int = 30) -> int:
        """Delete entries older than *older_than_days*. Returns count deleted."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        async with self._session_factory() as session:
            result = await session.execute(
                delete(DeadLetterEntryRow).where(
                    DeadLetterEntryRow.created_at < cutoff,
                )
            )
            await session.commit()
            return result.rowcount or 0
