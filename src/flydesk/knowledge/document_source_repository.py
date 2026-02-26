# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Repository for document source CRUD with encrypted config storage."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime

from cryptography.fernet import Fernet
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.models.document_source import DocumentSourceRow
from flydesk.security.kms import _DEV_FERNET_KEY

logger = logging.getLogger(__name__)


@dataclass
class DocumentSource:
    """Public-facing document source representation (config never exposed)."""

    id: str
    source_type: str
    category: str
    display_name: str
    auth_method: str
    has_config: bool
    config_summary: dict[str, str] | None  # Non-sensitive keys only
    is_active: bool
    sync_enabled: bool
    sync_cron: str | None
    last_sync_at: str | None
    created_at: str | None
    updated_at: str | None


# Keys that are safe to show in summaries
_SAFE_CONFIG_KEYS = {
    "bucket",
    "container",
    "prefix",
    "region",
    "project_id",
    "site_url",
    "library_name",
    "folder_id",
    "folder_path",
    "drive_id",
    "tenant_id",
}


class DocumentSourceRepository:
    """CRUD operations for document sources with Fernet-encrypted config."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        encryption_key: str = "",
    ) -> None:
        self._session_factory = session_factory
        self._fernet = self._build_fernet(encryption_key)

    @staticmethod
    def _build_fernet(encryption_key: str) -> Fernet:
        """Build a Fernet instance from the given key.

        If the key is empty or invalid, a dev-only key is used.
        """
        if encryption_key:
            try:
                return Fernet(
                    encryption_key.encode()
                    if isinstance(encryption_key, str)
                    else encryption_key
                )
            except ValueError:
                logger.warning(
                    "Invalid encryption key supplied; falling back to transient dev key."
                )
        return Fernet(_DEV_FERNET_KEY)

    def _encrypt(self, data: dict) -> str:
        return self._fernet.encrypt(json.dumps(data).encode()).decode()

    def _decrypt(self, token: str) -> dict:
        return json.loads(self._fernet.decrypt(token.encode()).decode())

    def _to_public(self, row: DocumentSourceRow) -> DocumentSource:
        try:
            config = self._decrypt(row.config_encrypted)
            summary = {k: v for k, v in config.items() if k in _SAFE_CONFIG_KEYS}
        except Exception:
            summary = None

        return DocumentSource(
            id=row.id,
            source_type=row.source_type,
            category=row.category,
            display_name=row.display_name,
            auth_method=row.auth_method,
            has_config=bool(row.config_encrypted),
            config_summary=summary,
            is_active=row.is_active,
            sync_enabled=row.sync_enabled,
            sync_cron=row.sync_cron,
            last_sync_at=row.last_sync_at.isoformat() if row.last_sync_at else None,
            created_at=row.created_at.isoformat() if row.created_at else None,
            updated_at=row.updated_at.isoformat() if row.updated_at else None,
        )

    async def create(
        self,
        *,
        source_type: str,
        category: str,
        display_name: str,
        auth_method: str,
        config: dict,
        sync_enabled: bool = False,
        sync_cron: str | None = None,
    ) -> DocumentSource:
        row = DocumentSourceRow(
            id=str(uuid.uuid4()),
            source_type=source_type,
            category=category,
            display_name=display_name,
            auth_method=auth_method,
            config_encrypted=self._encrypt(config),
            sync_enabled=sync_enabled,
            sync_cron=sync_cron,
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return self._to_public(row)

    async def get(self, source_id: str) -> DocumentSource | None:
        async with self._session_factory() as session:
            row = await session.get(DocumentSourceRow, source_id)
            if row is None:
                return None
            return self._to_public(row)

    async def get_decrypted_config(self, source_id: str) -> dict | None:
        async with self._session_factory() as session:
            row = await session.get(DocumentSourceRow, source_id)
            if row is None:
                return None
            return self._decrypt(row.config_encrypted)

    async def get_row(self, source_id: str) -> DocumentSourceRow | None:
        async with self._session_factory() as session:
            row = await session.get(DocumentSourceRow, source_id)
            if row is not None:
                await session.refresh(row)
                session.expunge(row)
            return row

    async def list_all(self) -> list[DocumentSource]:
        async with self._session_factory() as session:
            result = await session.execute(select(DocumentSourceRow))
            return [self._to_public(row) for row in result.scalars().all()]

    async def list_sync_enabled(self) -> list[DocumentSourceRow]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(DocumentSourceRow).where(
                    DocumentSourceRow.sync_enabled.is_(True),
                    DocumentSourceRow.is_active.is_(True),
                )
            )
            rows = list(result.scalars().all())
            for row in rows:
                session.expunge(row)
            return rows

    async def update(
        self,
        source_id: str,
        **kwargs,
    ) -> DocumentSource | None:
        async with self._session_factory() as session:
            row = await session.get(DocumentSourceRow, source_id)
            if row is None:
                return None
            allowed = {"display_name", "auth_method", "is_active", "sync_enabled", "sync_cron"}
            for key, value in kwargs.items():
                if key in allowed:
                    setattr(row, key, value)
            if "config" in kwargs and kwargs["config"] is not None:
                row.config_encrypted = self._encrypt(kwargs["config"])
            await session.commit()
            await session.refresh(row)
            return self._to_public(row)

    async def update_last_sync(self, source_id: str, last_sync_at: datetime | None) -> None:
        async with self._session_factory() as session:
            row = await session.get(DocumentSourceRow, source_id)
            if row:
                row.last_sync_at = last_sync_at
                await session.commit()

    async def delete(self, source_id: str) -> None:
        async with self._session_factory() as session:
            await session.execute(
                delete(DocumentSourceRow).where(DocumentSourceRow.id == source_id)
            )
            await session.commit()
