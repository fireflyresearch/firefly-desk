# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Persistence layer for Conversation Folders."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.models.conversation import ConversationRow
from flydesk.models.folder import ConversationFolderRow


def _from_json(value: Any) -> dict | list:
    """Deserialize a value that may be a JSON string (SQLite) or already a dict/list."""
    if isinstance(value, str):
        return json.loads(value)
    return value if value is not None else {}


def _to_json(value: Any) -> str | None:
    """Serialize a Python object to a JSON string for SQLite Text columns."""
    if value is None:
        return None
    return json.dumps(value, default=str)


class FolderRepository:
    """CRUD operations for conversation folders."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_folders(self, user_id: str) -> list[dict[str, Any]]:
        """Return folders for a user, sorted by sort_order."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(ConversationFolderRow)
                .where(ConversationFolderRow.user_id == user_id)
                .order_by(ConversationFolderRow.sort_order.asc())
            )
            return [
                {
                    "id": row.id,
                    "name": row.name,
                    "icon": row.icon,
                    "sort_order": row.sort_order,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in result.scalars().all()
            ]

    async def create_folder(self, user_id: str, name: str, icon: str = "folder") -> dict[str, Any]:
        """Create a new folder and return it."""
        async with self._session_factory() as session:
            # Determine next sort_order
            from sqlalchemy import func

            count_result = await session.execute(
                select(func.count()).where(ConversationFolderRow.user_id == user_id)
            )
            next_order = (count_result.scalar() or 0)

            folder_id = str(uuid.uuid4())
            row = ConversationFolderRow(
                id=folder_id,
                user_id=user_id,
                name=name,
                icon=icon,
                sort_order=next_order,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return {
                "id": row.id,
                "name": row.name,
                "icon": row.icon,
                "sort_order": row.sort_order,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }

    async def update_folder(
        self, folder_id: str, user_id: str, name: str, icon: str | None = None
    ) -> None:
        """Update a folder's name and optionally its icon, only if owned by user."""
        values: dict[str, Any] = {"name": name}
        if icon is not None:
            values["icon"] = icon
        async with self._session_factory() as session:
            await session.execute(
                update(ConversationFolderRow)
                .where(
                    ConversationFolderRow.id == folder_id,
                    ConversationFolderRow.user_id == user_id,
                )
                .values(**values)
            )
            await session.commit()

    async def delete_folder(self, folder_id: str, user_id: str) -> None:
        """Delete a folder and unset folder_id in affected conversations' metadata."""
        async with self._session_factory() as session:
            # First, unset folder_id in conversations that reference this folder
            convs_result = await session.execute(
                select(ConversationRow).where(
                    ConversationRow.user_id == user_id,
                    ConversationRow.status != "deleted",
                )
            )
            for conv_row in convs_result.scalars().all():
                metadata = _from_json(conv_row.metadata_) if conv_row.metadata_ else {}
                if isinstance(metadata, dict) and metadata.get("folder_id") == folder_id:
                    metadata.pop("folder_id", None)
                    conv_row.metadata_ = _to_json(metadata)

            # Delete the folder
            folder_result = await session.execute(
                select(ConversationFolderRow).where(
                    ConversationFolderRow.id == folder_id,
                    ConversationFolderRow.user_id == user_id,
                )
            )
            folder_row = folder_result.scalar_one_or_none()
            if folder_row is not None:
                await session.delete(folder_row)

            await session.commit()

    async def reorder_folders(
        self, user_id: str, folder_ids: list[str]
    ) -> None:
        """Bulk update sort_order based on the order of folder_ids."""
        async with self._session_factory() as session:
            for idx, fid in enumerate(folder_ids):
                await session.execute(
                    update(ConversationFolderRow)
                    .where(
                        ConversationFolderRow.id == fid,
                        ConversationFolderRow.user_id == user_id,
                    )
                    .values(sort_order=idx)
                )
            await session.commit()
