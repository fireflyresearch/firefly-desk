# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Append-only audit logger with PII sanitization."""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.audit.models import AuditEvent
from flydesk.models.audit import AuditEventRow


def _to_json(value: Any) -> str | None:
    """Serialize a Python object to a JSON string for SQLite Text columns.

    JSONB handles serialization natively on PostgreSQL, but when using the
    ``Text`` variant (SQLite) the caller must provide a plain string.
    """
    if value is None:
        return None
    return json.dumps(value, default=str)

# Patterns for PII sanitization
_EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
_PHONE_PATTERN = re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b')
_SSN_PATTERN = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')


class AuditLogger:
    """Append-only audit logger with PII sanitization."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def log(self, event: AuditEvent) -> str:
        """Log an audit event. Returns the event ID."""
        sanitized_detail = self._sanitize(event.detail)
        async with self._session_factory() as session:
            row = AuditEventRow(
                event_type=event.event_type.value,
                user_id=event.user_id,
                conversation_id=event.conversation_id,
                system_id=event.system_id,
                endpoint_id=event.endpoint_id,
                action=event.action,
                detail=_to_json(sanitized_detail),
                risk_level=event.risk_level,
                ip_address=event.ip_address,
                user_agent=event.user_agent,
            )
            session.add(row)
            await session.commit()
            return row.id

    async def get_event(self, event_id: str) -> AuditEvent | None:
        """Retrieve a single audit event by ID."""
        async with self._session_factory() as session:
            row = await session.get(AuditEventRow, event_id)
            if row is None:
                return None
            return self._row_to_event(row)

    async def query(
        self,
        *,
        user_id: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[AuditEvent]:
        """Query audit events with optional filters."""
        async with self._session_factory() as session:
            stmt = select(AuditEventRow).order_by(AuditEventRow.created_at.desc())
            if user_id:
                stmt = stmt.where(AuditEventRow.user_id == user_id)
            if event_type:
                stmt = stmt.where(AuditEventRow.event_type == event_type)
            stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            return [self._row_to_event(r) for r in result.scalars().all()]

    @classmethod
    def _sanitize(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Sanitize PII from audit detail data."""
        sanitized = {}
        for key, value in data.items():
            if isinstance(value, str):
                sanitized[key] = cls._sanitize_string(value)
            elif isinstance(value, dict):
                sanitized[key] = cls._sanitize(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    cls._sanitize_string(v) if isinstance(v, str)
                    else cls._sanitize(v) if isinstance(v, dict)
                    else v
                    for v in value
                ]
            else:
                sanitized[key] = value
        return sanitized

    @staticmethod
    def _sanitize_string(value: str) -> str:
        """Replace PII patterns in a string."""
        value = _EMAIL_PATTERN.sub("[EMAIL]", value)
        value = _PHONE_PATTERN.sub("[PHONE]", value)
        value = _SSN_PATTERN.sub("[SSN]", value)
        return value

    @staticmethod
    def _row_to_event(row: AuditEventRow) -> AuditEvent:
        detail = row.detail
        if isinstance(detail, str):
            detail = json.loads(detail)
        return AuditEvent(
            id=row.id,
            timestamp=row.created_at,
            event_type=row.event_type,
            user_id=row.user_id,
            conversation_id=row.conversation_id,
            system_id=row.system_id,
            endpoint_id=row.endpoint_id,
            action=row.action,
            detail=detail,
            risk_level=row.risk_level,
            ip_address=row.ip_address,
            user_agent=row.user_agent,
        )
