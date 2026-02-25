# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Persistence layer for custom tools."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.models.custom_tool import CustomToolRow
from flydesk.tools.custom_models import CustomTool, ToolSource

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_json(value: Any) -> str | None:
    """Serialize a Python object to a JSON string for SQLite Text columns.

    JSONB handles serialization natively on PostgreSQL, but when using the
    ``Text`` variant (SQLite) the caller must provide a plain string.
    """
    if value is None:
        return None
    return json.dumps(value, default=str)


def _from_json(value: Any) -> dict | list | None:
    if value is None:
        return None
    if isinstance(value, str):
        return json.loads(value)
    return value


class CustomToolRepository:
    """CRUD operations for custom tools."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, tool: CustomTool) -> CustomTool:
        now = _utcnow()
        async with self._session_factory() as session:
            row = CustomToolRow(
                id=tool.id,
                name=tool.name,
                description=tool.description,
                python_code=tool.python_code,
                parameters=_to_json(tool.parameters),
                output_schema=_to_json(tool.output_schema),
                active=tool.active,
                source=tool.source.value,
                timeout_seconds=tool.timeout_seconds,
                max_memory_mb=tool.max_memory_mb,
                created_by=tool.created_by,
                created_at=tool.created_at or now,
                updated_at=tool.updated_at or now,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return self._row_to_tool(row)

    async def get(self, tool_id: str) -> CustomTool | None:
        async with self._session_factory() as session:
            row = await session.get(CustomToolRow, tool_id)
            if row is None:
                return None
            return self._row_to_tool(row)

    async def get_by_name(self, name: str) -> CustomTool | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(CustomToolRow).where(CustomToolRow.name == name)
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return self._row_to_tool(row)

    async def list(
        self,
        *,
        source: ToolSource | None = None,
        active_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CustomTool]:
        async with self._session_factory() as session:
            stmt = select(CustomToolRow)
            if source is not None:
                stmt = stmt.where(CustomToolRow.source == source.value)
            if active_only:
                stmt = stmt.where(CustomToolRow.active.is_(True))
            stmt = stmt.order_by(CustomToolRow.name).limit(limit).offset(offset)
            result = await session.execute(stmt)
            return [self._row_to_tool(r) for r in result.scalars().all()]

    async def update(self, tool: CustomTool) -> CustomTool:
        async with self._session_factory() as session:
            row = await session.get(CustomToolRow, tool.id)
            if row is None:
                raise ValueError(f"Tool {tool.id!r} not found")
            row.name = tool.name
            row.description = tool.description
            row.python_code = tool.python_code
            row.parameters = _to_json(tool.parameters)
            row.output_schema = _to_json(tool.output_schema)
            row.active = tool.active
            row.timeout_seconds = tool.timeout_seconds
            row.max_memory_mb = tool.max_memory_mb
            row.updated_at = _utcnow()
            await session.commit()
            await session.refresh(row)
            return self._row_to_tool(row)

    async def delete(self, tool_id: str) -> bool:
        async with self._session_factory() as session:
            row = await session.get(CustomToolRow, tool_id)
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True

    @staticmethod
    def _row_to_tool(row: CustomToolRow) -> CustomTool:
        return CustomTool(
            id=row.id,
            name=row.name,
            description=row.description,
            python_code=row.python_code,
            parameters=_from_json(row.parameters) or {},
            output_schema=_from_json(row.output_schema) or {},
            active=row.active,
            source=ToolSource(row.source),
            timeout_seconds=row.timeout_seconds,
            max_memory_mb=row.max_memory_mb,
            created_by=row.created_by,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
