# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Persistence layer for LLM provider configuration."""

from __future__ import annotations

import base64
import json
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.llm.models import LLMModel, LLMProvider, ProviderType
from flydesk.models.llm import LLMProviderRow


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


class LLMProviderRepository:
    """CRUD operations for LLM provider configuration."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        encryption_key: str = "",
    ) -> None:
        self._session_factory = session_factory
        self._encryption_key = encryption_key

    # -- Encryption helpers --

    def _encrypt(self, plaintext: str | None) -> str | None:
        """Encrypt an API key using base64 obfuscation.

        A real deployment should use Fernet or a KMS. For now we use base64
        encoding as a basic obfuscation layer.
        """
        if plaintext is None:
            return None
        return base64.b64encode(plaintext.encode()).decode()

    def _decrypt(self, ciphertext: str | None) -> str | None:
        """Decrypt an API key."""
        if ciphertext is None:
            return None
        return base64.b64decode(ciphertext.encode()).decode()

    # -- CRUD --

    async def create_provider(self, provider: LLMProvider) -> None:
        """Persist a new LLM provider."""
        async with self._session_factory() as session:
            row = LLMProviderRow(
                id=provider.id,
                name=provider.name,
                provider_type=provider.provider_type.value,
                api_key_encrypted=self._encrypt(provider.api_key),
                base_url=provider.base_url,
                models=_to_json([m.model_dump() for m in provider.models]),
                default_model=provider.default_model,
                capabilities=_to_json(provider.capabilities),
                config=_to_json(provider.config),
                is_default=provider.is_default,
                is_active=provider.is_active,
            )
            session.add(row)
            await session.commit()

    async def get_provider(self, provider_id: str) -> LLMProvider | None:
        """Retrieve an LLM provider by ID, or ``None`` if not found."""
        async with self._session_factory() as session:
            row = await session.get(LLMProviderRow, provider_id)
            if row is None:
                return None
            return self._row_to_provider(row)

    async def get_default_provider(self) -> LLMProvider | None:
        """Retrieve the default LLM provider, or ``None`` if none is set."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(LLMProviderRow).where(LLMProviderRow.is_default.is_(True))
            )
            row = result.scalars().first()
            if row is None:
                return None
            return self._row_to_provider(row)

    async def list_providers(self) -> list[LLMProvider]:
        """Return every registered LLM provider."""
        async with self._session_factory() as session:
            result = await session.execute(select(LLMProviderRow))
            return [self._row_to_provider(r) for r in result.scalars().all()]

    async def update_provider(self, provider: LLMProvider) -> None:
        """Update an existing LLM provider (raises ``ValueError`` if missing)."""
        async with self._session_factory() as session:
            row = await session.get(LLMProviderRow, provider.id)
            if row is None:
                msg = f"Provider {provider.id} not found"
                raise ValueError(msg)
            row.name = provider.name
            row.provider_type = provider.provider_type.value
            # Only update the API key if a new one is provided
            if provider.api_key is not None:
                row.api_key_encrypted = self._encrypt(provider.api_key)
            row.base_url = provider.base_url
            row.models = _to_json([m.model_dump() for m in provider.models])
            row.default_model = provider.default_model
            row.capabilities = _to_json(provider.capabilities)
            row.config = _to_json(provider.config)
            row.is_default = provider.is_default
            row.is_active = provider.is_active
            await session.commit()

    async def delete_provider(self, provider_id: str) -> None:
        """Delete an LLM provider by ID."""
        async with self._session_factory() as session:
            await session.execute(
                delete(LLMProviderRow).where(LLMProviderRow.id == provider_id)
            )
            await session.commit()

    async def set_default(self, provider_id: str) -> None:
        """Set a provider as the default, unsetting all others."""
        async with self._session_factory() as session:
            # Unset all defaults
            await session.execute(
                update(LLMProviderRow)
                .where(LLMProviderRow.is_default.is_(True))
                .values(is_default=False)
            )
            # Set the chosen provider as default
            await session.execute(
                update(LLMProviderRow)
                .where(LLMProviderRow.id == provider_id)
                .values(is_default=True)
            )
            await session.commit()

    # -- Mapping helper --

    def _row_to_provider(self, row: LLMProviderRow) -> LLMProvider:
        raw_models = _from_json(row.models) if row.models else []
        models = [LLMModel(**m) if isinstance(m, dict) else m for m in raw_models]
        return LLMProvider(
            id=row.id,
            name=row.name,
            provider_type=ProviderType(row.provider_type),
            api_key=self._decrypt(row.api_key_encrypted),
            base_url=row.base_url,
            models=models,
            default_model=row.default_model,
            capabilities=_from_json(row.capabilities) if row.capabilities else {},
            config=_from_json(row.config) if row.config else {},
            is_default=row.is_default,
            is_active=row.is_active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
