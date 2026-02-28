# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Persistence layer for user and application settings."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.models.user_settings import AppSettingRow, UserSettingRow
from flydesk.settings.models import AgentSettings, EmailSettings, UserSettings


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


class SettingsRepository:
    """CRUD operations for user and application settings."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    # -- User Settings --

    async def get_user_settings(self, user_id: str) -> UserSettings:
        """Retrieve settings for a user, returning defaults if not found."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(UserSettingRow).where(UserSettingRow.user_id == user_id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                return UserSettings()
            settings_data = _from_json(row.settings)
            return UserSettings(**settings_data)

    async def update_user_settings(self, user_id: str, settings: UserSettings) -> None:
        """Upsert user settings -- creates the row if it does not exist."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(UserSettingRow).where(UserSettingRow.user_id == user_id)
            )
            row = result.scalar_one_or_none()
            settings_json = _to_json(settings.model_dump())
            if row is None:
                row = UserSettingRow(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    settings=settings_json,
                )
                session.add(row)
            else:
                row.settings = settings_json
            await session.commit()

    # -- App Settings --

    async def get_app_setting(self, key: str) -> str | None:
        """Retrieve a single app setting by key, or ``None`` if not found."""
        async with self._session_factory() as session:
            row = await session.get(AppSettingRow, key)
            if row is None:
                return None
            return row.value

    async def set_app_setting(
        self, key: str, value: str, category: str = "general"
    ) -> None:
        """Upsert an app setting."""
        async with self._session_factory() as session:
            row = await session.get(AppSettingRow, key)
            if row is None:
                row = AppSettingRow(key=key, value=value, category=category)
                session.add(row)
            else:
                row.value = value
                row.category = category
            await session.commit()

    async def get_all_app_settings(
        self, category: str | None = None
    ) -> dict[str, str]:
        """Return all app settings, optionally filtered by category."""
        async with self._session_factory() as session:
            stmt = select(AppSettingRow)
            if category is not None:
                stmt = stmt.where(AppSettingRow.category == category)
            result = await session.execute(stmt)
            return {row.key: row.value for row in result.scalars().all()}

    # -- Agent Settings --

    async def get_agent_settings(self) -> AgentSettings:
        """Retrieve agent customization settings from the ``agent`` category.

        Returns :class:`AgentSettings` with defaults for any keys not stored
        in the database.
        """
        raw = await self.get_all_app_settings(category="agent")
        if not raw:
            return AgentSettings()

        # Convert the flat key-value store into AgentSettings fields.
        data: dict[str, Any] = {}
        for field_name in AgentSettings.model_fields:
            if field_name in raw:
                field_info = AgentSettings.model_fields[field_name]
                raw_val = raw[field_name]
                # Deserialize list/complex fields from JSON
                if field_info.annotation is list or (
                    hasattr(field_info.annotation, "__origin__")
                    and getattr(field_info.annotation, "__origin__", None) is list
                ):
                    data[field_name] = json.loads(raw_val) if raw_val else []
                elif field_info.annotation is bool:
                    data[field_name] = raw_val.lower() in ("true", "1")
                else:
                    data[field_name] = raw_val
        return AgentSettings(**data)

    async def set_agent_settings(self, settings: AgentSettings) -> None:
        """Persist agent customization settings under the ``agent`` category.

        Each field of :class:`AgentSettings` is stored as a separate
        key-value pair so individual values can be read independently.
        """
        dumped = settings.model_dump()
        for key, value in dumped.items():
            if isinstance(value, (list, dict)):
                str_value = json.dumps(value)
            else:
                str_value = str(value)
            await self.set_app_setting(key, str_value, category="agent")

    # -- Email Settings --

    async def get_email_settings(self) -> EmailSettings:
        """Retrieve email channel settings from the ``email`` category."""
        raw = await self.get_all_app_settings(category="email")
        if not raw:
            return EmailSettings()

        data: dict[str, Any] = {}
        for field_name in EmailSettings.model_fields:
            if field_name in raw:
                field_info = EmailSettings.model_fields[field_name]
                raw_val = raw[field_name]
                if field_info.annotation is list or (
                    hasattr(field_info.annotation, "__origin__")
                    and getattr(field_info.annotation, "__origin__", None) is list
                ):
                    data[field_name] = json.loads(raw_val) if raw_val else []
                elif field_info.annotation is bool:
                    data[field_name] = raw_val.lower() in ("true", "1")
                elif field_info.annotation is int:
                    data[field_name] = int(raw_val)
                else:
                    data[field_name] = raw_val
        return EmailSettings(**data)

    async def set_email_settings(self, settings: EmailSettings) -> None:
        """Persist email channel settings under the ``email`` category."""
        dumped = settings.model_dump()
        for key, value in dumped.items():
            if isinstance(value, (list, dict)):
                str_value = json.dumps(value)
            else:
                str_value = str(value)
            await self.set_app_setting(key, str_value, category="email")

    # -- Callback Settings --

    async def get_callbacks(self) -> list[dict]:
        """Return all callback configurations from their own category."""
        raw = await self.get_app_setting("callbacks_list")
        if raw:
            return json.loads(raw)
        return []

    async def set_callbacks(self, callbacks: list[dict]) -> None:
        """Persist callback configurations in their own category."""
        await self.set_app_setting(
            "callbacks_list", json.dumps(callbacks, default=str), category="callbacks"
        )
