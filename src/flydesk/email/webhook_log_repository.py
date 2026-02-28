# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Database-backed persistence for inbound webhook log entries."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.email.webhook_log import WebhookLogEntry
from flydesk.models.webhook_log import WebhookLogEntryRow


class WebhookLogRepository:
    """CRUD operations for webhook log entries."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def record(self, entry: WebhookLogEntry) -> str:
        """Persist a webhook log entry and return its ID."""
        async with self._session_factory() as session:
            row = WebhookLogEntryRow(
                id=entry.id,
                provider=entry.provider,
                status=entry.status,
                from_address=entry.from_address,
                subject=entry.subject,
                payload_preview=entry.payload_preview,
                processing_ms=entry.processing_time_ms,
                error=entry.error,
                created_at=entry.timestamp,
            )
            session.add(row)
            await session.commit()
            return row.id

    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        provider: str | None = None,
    ) -> list[WebhookLogEntry]:
        """Return entries newest-first, with optional filters."""
        async with self._session_factory() as session:
            stmt = select(WebhookLogEntryRow)
            if status is not None:
                stmt = stmt.where(WebhookLogEntryRow.status == status)
            if provider is not None:
                stmt = stmt.where(WebhookLogEntryRow.provider == provider)
            stmt = stmt.order_by(WebhookLogEntryRow.created_at.desc()).limit(limit).offset(offset)
            result = await session.execute(stmt)
            return [self._row_to_entry(r) for r in result.scalars().all()]

    async def get(self, entry_id: str) -> WebhookLogEntry | None:
        """Retrieve a single entry by ID, or ``None`` if not found."""
        async with self._session_factory() as session:
            row = await session.get(WebhookLogEntryRow, entry_id)
            if row is None:
                return None
            return self._row_to_entry(row)

    async def clear(self) -> int:
        """Delete all entries. Returns the number of rows deleted."""
        async with self._session_factory() as session:
            result = await session.execute(delete(WebhookLogEntryRow))
            await session.commit()
            return result.rowcount  # type: ignore[return-value]

    async def cleanup(self, older_than_days: int = 30) -> int:
        """Delete entries older than *older_than_days*. Returns the count deleted."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        async with self._session_factory() as session:
            result = await session.execute(
                delete(WebhookLogEntryRow).where(WebhookLogEntryRow.created_at < cutoff)
            )
            await session.commit()
            return result.rowcount  # type: ignore[return-value]

    @staticmethod
    def _row_to_entry(row: WebhookLogEntryRow) -> WebhookLogEntry:
        return WebhookLogEntry(
            id=row.id,
            timestamp=row.created_at,
            provider=row.provider,
            status=row.status,
            from_address=row.from_address,
            subject=row.subject,
            payload_preview=row.payload_preview,
            processing_time_ms=row.processing_ms,
            error=row.error,
        )
