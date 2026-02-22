# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Persistence layer for exports and export templates."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydek.exports.models import ExportFormat, ExportRecord, ExportStatus, ExportTemplate
from flydek.models.export import ExportRow, ExportTemplateRow


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


class ExportRepository:
    """CRUD operations for exports and export templates."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    # -- Exports --

    async def create_export(self, record: ExportRecord) -> None:
        """Persist a new export record."""
        async with self._session_factory() as session:
            row = ExportRow(
                id=record.id,
                user_id=record.user_id,
                format=record.format.value,
                template_id=record.template_id,
                title=record.title,
                description=record.description,
                status=record.status.value,
                file_path=record.file_path,
                file_size=record.file_size,
                row_count=record.row_count,
                error=record.error,
                source_data=_to_json(record.source_data),
            )
            session.add(row)
            await session.commit()

    async def get_export(self, export_id: str) -> ExportRecord | None:
        """Retrieve an export record by ID, or ``None`` if not found."""
        async with self._session_factory() as session:
            row = await session.get(ExportRow, export_id)
            if row is None:
                return None
            return self._row_to_export(row)

    async def list_exports(
        self,
        user_id: str,
        *,
        limit: int = 50,
    ) -> list[ExportRecord]:
        """Return exports for a user, most recent first."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(ExportRow)
                .where(ExportRow.user_id == user_id)
                .order_by(ExportRow.created_at.desc())
                .limit(limit)
            )
            return [self._row_to_export(r) for r in result.scalars().all()]

    async def update_export(self, record: ExportRecord) -> None:
        """Update an existing export record."""
        async with self._session_factory() as session:
            row = await session.get(ExportRow, record.id)
            if row is None:
                msg = f"Export {record.id} not found"
                raise ValueError(msg)
            row.status = record.status.value
            row.file_path = record.file_path
            row.file_size = record.file_size
            row.row_count = record.row_count
            row.error = record.error
            row.completed_at = record.completed_at
            await session.commit()

    async def delete_export(self, export_id: str) -> None:
        """Delete an export record."""
        async with self._session_factory() as session:
            await session.execute(
                delete(ExportRow).where(ExportRow.id == export_id)
            )
            await session.commit()

    # -- Templates --

    async def create_template(self, template: ExportTemplate) -> None:
        """Persist a new export template."""
        async with self._session_factory() as session:
            row = ExportTemplateRow(
                id=template.id,
                name=template.name,
                format=template.format.value,
                column_mapping=_to_json(template.column_mapping),
                header_text=template.header_text,
                footer_text=template.footer_text,
                is_system=template.is_system,
            )
            session.add(row)
            await session.commit()

    async def get_template(self, template_id: str) -> ExportTemplate | None:
        """Retrieve a template by ID, or ``None`` if not found."""
        async with self._session_factory() as session:
            row = await session.get(ExportTemplateRow, template_id)
            if row is None:
                return None
            return self._row_to_template(row)

    async def list_templates(self) -> list[ExportTemplate]:
        """Return all export templates."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(ExportTemplateRow).order_by(ExportTemplateRow.name.asc())
            )
            return [self._row_to_template(r) for r in result.scalars().all()]

    async def delete_template(self, template_id: str) -> None:
        """Delete an export template."""
        async with self._session_factory() as session:
            await session.execute(
                delete(ExportTemplateRow).where(ExportTemplateRow.id == template_id)
            )
            await session.commit()

    # -- Mapping helpers --

    @staticmethod
    def _row_to_export(row: ExportRow) -> ExportRecord:
        return ExportRecord(
            id=row.id,
            user_id=row.user_id,
            format=ExportFormat(row.format),
            template_id=row.template_id,
            title=row.title,
            description=row.description,
            status=ExportStatus(row.status),
            file_path=row.file_path,
            file_size=row.file_size,
            row_count=row.row_count,
            error=row.error,
            source_data=_from_json(row.source_data) if row.source_data else {},
            created_at=row.created_at,
            completed_at=row.completed_at,
        )

    @staticmethod
    def _row_to_template(row: ExportTemplateRow) -> ExportTemplate:
        return ExportTemplate(
            id=row.id,
            name=row.name,
            format=ExportFormat(row.format),
            column_mapping=_from_json(row.column_mapping) if row.column_mapping else {},
            header_text=row.header_text,
            footer_text=row.footer_text,
            is_system=row.is_system,
            created_at=row.created_at,
        )
