# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Persistence layer for file uploads."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydek.files.models import FileUpload
from flydek.models.file_upload import FileUploadRow


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


class FileUploadRepository:
    """CRUD operations for file uploads."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, upload: FileUpload) -> None:
        """Persist a new file upload record."""
        async with self._session_factory() as session:
            row = FileUploadRow(
                id=upload.id,
                conversation_id=upload.conversation_id,
                user_id=upload.user_id,
                filename=upload.filename,
                content_type=upload.content_type,
                file_size=upload.file_size,
                storage_path=upload.storage_path,
                storage_backend=upload.storage_backend,
                extracted_text=upload.extracted_text,
                metadata_=_to_json(upload.metadata),
            )
            session.add(row)
            await session.commit()

    async def get(self, file_id: str) -> FileUpload | None:
        """Retrieve a file upload by ID, or ``None`` if not found."""
        async with self._session_factory() as session:
            row = await session.get(FileUploadRow, file_id)
            if row is None:
                return None
            return self._row_to_upload(row)

    async def list_by_conversation(self, conversation_id: str) -> list[FileUpload]:
        """Return all file uploads associated with a conversation."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(FileUploadRow)
                .where(FileUploadRow.conversation_id == conversation_id)
                .order_by(FileUploadRow.created_at.asc())
            )
            return [self._row_to_upload(r) for r in result.scalars().all()]

    async def delete(self, file_id: str) -> None:
        """Delete a file upload record."""
        async with self._session_factory() as session:
            await session.execute(
                delete(FileUploadRow).where(FileUploadRow.id == file_id)
            )
            await session.commit()

    @staticmethod
    def _row_to_upload(row: FileUploadRow) -> FileUpload:
        return FileUpload(
            id=row.id,
            conversation_id=row.conversation_id,
            user_id=row.user_id,
            filename=row.filename,
            content_type=row.content_type,
            file_size=row.file_size,
            storage_path=row.storage_path,
            storage_backend=row.storage_backend,
            extracted_text=row.extracted_text,
            metadata=_from_json(row.metadata_) if row.metadata_ else {},
            created_at=row.created_at,
        )
