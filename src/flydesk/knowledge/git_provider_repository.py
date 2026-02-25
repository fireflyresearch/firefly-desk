# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Persistence layer for Git provider configuration."""

from __future__ import annotations

import base64 as _b64
import json
import logging
import uuid
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.models.git_provider import GitProviderRow

logger = logging.getLogger(__name__)

# Dev-only Fernet key (used when no encryption key is configured).
# This is **not** secure and exists only so that dev mode doesn't crash.
# Must be a static, deterministic key so encrypted values survive restarts.
_DEV_FERNET_KEY = _b64.urlsafe_b64encode(b"flydesk-dev-encryption-key-32b!!")


def _to_json(value: Any) -> str | None:
    """Serialize a Python object to a JSON string for SQLite Text columns."""
    if value is None:
        return None
    return json.dumps(value, default=str)


def _from_json(value: Any) -> list | dict:
    """Deserialize a value that may be a JSON string (SQLite) or already a dict/list."""
    if isinstance(value, str):
        return json.loads(value)
    if value is None:
        return []
    return value


# Fields that may be modified via update_provider().  Anything outside
# this set is silently ignored, preventing callers from overwriting
# internal columns like ``id`` or ``client_secret_encrypted``.
_UPDATABLE_FIELDS: frozenset[str] = frozenset({
    "provider_type",
    "display_name",
    "base_url",
    "client_id",
    "oauth_authorize_url",
    "oauth_token_url",
    "is_active",
})


class GitProviderRepository:
    """CRUD operations for persisted Git provider configuration."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        encryption_key: str = "",
    ) -> None:
        self._session_factory = session_factory
        self._fernet = self._build_fernet(encryption_key)

    # -- Encryption helpers --

    @staticmethod
    def _build_fernet(encryption_key: str) -> Fernet:
        """Build a Fernet instance from the given key.

        If the key is empty or invalid, a dev-only key is used.
        """
        if encryption_key:
            try:
                # Fernet keys must be 32 url-safe base64-encoded bytes
                return Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
            except (ValueError, Exception):
                logger.warning(
                    "Invalid encryption key supplied; falling back to transient dev key."
                )
        return Fernet(_DEV_FERNET_KEY)

    def _encrypt(self, plaintext: str | None) -> str | None:
        if plaintext is None:
            return None
        return self._fernet.encrypt(plaintext.encode()).decode()

    def _decrypt(self, ciphertext: str | None) -> str | None:
        if ciphertext is None:
            return None
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken:
            logger.warning("Failed to decrypt Git provider client secret; returning None.")
            return None

    # -- CRUD --

    async def create_provider(
        self,
        *,
        provider_type: str,
        display_name: str,
        base_url: str,
        client_id: str,
        client_secret: str | None = None,
        oauth_authorize_url: str | None = None,
        oauth_token_url: str | None = None,
        scopes: list[str] | None = None,
        is_active: bool = True,
    ) -> GitProviderRow:
        """Persist a new Git provider configuration."""
        row = GitProviderRow(
            id=str(uuid.uuid4()),
            provider_type=provider_type,
            display_name=display_name,
            base_url=base_url,
            client_id=client_id,
            client_secret_encrypted=self._encrypt(client_secret),
            oauth_authorize_url=oauth_authorize_url,
            oauth_token_url=oauth_token_url,
            scopes=_to_json(scopes) if scopes else None,
            is_active=is_active,
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return row

    async def get_provider(self, provider_id: str) -> GitProviderRow | None:
        """Retrieve a Git provider by ID."""
        async with self._session_factory() as session:
            return await session.get(GitProviderRow, provider_id)

    async def list_providers(self) -> list[GitProviderRow]:
        """Return all Git providers."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(GitProviderRow).order_by(GitProviderRow.display_name)
            )
            return list(result.scalars().all())

    async def update_provider(
        self,
        provider_id: str,
        **kwargs: Any,
    ) -> GitProviderRow | None:
        """Update fields on an existing Git provider."""
        async with self._session_factory() as session:
            row = await session.get(GitProviderRow, provider_id)
            if row is None:
                return None

            for key, value in kwargs.items():
                if key == "client_secret":
                    row.client_secret_encrypted = self._encrypt(value)
                elif key == "scopes":
                    row.scopes = _to_json(value) if value else None
                elif key in _UPDATABLE_FIELDS:
                    setattr(row, key, value)

            await session.commit()
            await session.refresh(row)
            return row

    async def delete_provider(self, provider_id: str) -> None:
        """Delete a Git provider by ID."""
        async with self._session_factory() as session:
            await session.execute(
                delete(GitProviderRow).where(GitProviderRow.id == provider_id)
            )
            await session.commit()

    def decrypt_secret(self, row: GitProviderRow) -> str | None:
        """Decrypt the client_secret for a provider row."""
        return self._decrypt(row.client_secret_encrypted)

    def parse_scopes(self, row: GitProviderRow) -> list[str]:
        """Parse the JSON scopes stored on a row."""
        if row.scopes is None:
            return []
        return _from_json(row.scopes)  # type: ignore[return-value]
