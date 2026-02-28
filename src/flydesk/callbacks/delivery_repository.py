# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Persistence layer for outbound callback delivery attempts."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.models.callback_delivery import CallbackDeliveryRow

logger = logging.getLogger(__name__)


def _to_json(value: Any) -> str | None:
    """Serialize a Python object to a JSON string for SQLite Text columns."""
    if value is None:
        return None
    return json.dumps(value, default=str)


def _from_json(value: Any) -> dict | list | None:
    """Deserialize a value that may be a JSON string (SQLite) or already a dict/list."""
    if value is None:
        return None
    if isinstance(value, str):
        return json.loads(value)
    return value


class CallbackDeliveryRepository:
    """CRUD operations for outbound callback delivery log entries."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def record(
        self,
        *,
        callback_id: str,
        event: str,
        url: str,
        attempt: int = 1,
        status: str,
        status_code: int | None = None,
        error: str | None = None,
        payload: dict | None = None,
    ) -> str:
        """Persist a new delivery attempt and return its ID."""
        row_id = str(uuid.uuid4())
        async with self._session_factory() as session:
            row = CallbackDeliveryRow(
                id=row_id,
                callback_id=callback_id,
                event=event,
                url=url,
                attempt=attempt,
                status=status,
                status_code=status_code,
                error=error,
                payload_json=_to_json(payload),
            )
            session.add(row)
            await session.commit()
        return row_id

    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        callback_id: str | None = None,
        event: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        """Return delivery log entries, optionally filtered, most recent first."""
        async with self._session_factory() as session:
            stmt = select(CallbackDeliveryRow)
            if callback_id is not None:
                stmt = stmt.where(CallbackDeliveryRow.callback_id == callback_id)
            if event is not None:
                stmt = stmt.where(CallbackDeliveryRow.event == event)
            if status is not None:
                stmt = stmt.where(CallbackDeliveryRow.status == status)
            stmt = stmt.order_by(CallbackDeliveryRow.created_at.desc()).limit(limit).offset(offset)
            result = await session.execute(stmt)
            return [self._row_to_dict(r) for r in result.scalars().all()]

    async def clear(self) -> int:
        """Delete all delivery log entries. Returns the number of rows deleted."""
        async with self._session_factory() as session:
            result = await session.execute(delete(CallbackDeliveryRow))
            await session.commit()
            return result.rowcount  # type: ignore[return-value]

    async def cleanup(self, older_than_days: int = 30) -> int:
        """Delete delivery log entries older than *older_than_days*.

        Returns the number of rows deleted.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        async with self._session_factory() as session:
            result = await session.execute(
                delete(CallbackDeliveryRow).where(
                    CallbackDeliveryRow.created_at < cutoff,
                )
            )
            await session.commit()
            return result.rowcount  # type: ignore[return-value]

    @staticmethod
    def _row_to_dict(row: CallbackDeliveryRow) -> dict:
        return {
            "id": row.id,
            "callback_id": row.callback_id,
            "event": row.event,
            "url": row.url,
            "attempt": row.attempt,
            "status": row.status,
            "status_code": row.status_code,
            "error": row.error,
            "payload": _from_json(row.payload_json),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
