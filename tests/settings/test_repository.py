# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for SettingsRepository."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.models.base import Base
from flydesk.settings.models import UserSettings
from flydesk.settings.repository import SettingsRepository


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def repo(session_factory):
    return SettingsRepository(session_factory)


class TestUserSettings:
    async def test_get_user_settings_defaults(self, repo):
        """When no settings are saved, defaults should be returned."""
        settings = await repo.get_user_settings("user-1")
        assert settings.theme == "system"
        assert settings.agent_verbose is False
        assert settings.sidebar_collapsed is False
        assert settings.notifications_enabled is True
        assert settings.default_model_id is None

    async def test_update_and_get_user_settings(self, repo):
        """Saved settings should be returned on subsequent reads."""
        custom = UserSettings(
            theme="dark",
            agent_verbose=True,
            sidebar_collapsed=True,
            notifications_enabled=False,
            default_model_id="gpt-4o",
        )
        await repo.update_user_settings("user-1", custom)

        result = await repo.get_user_settings("user-1")
        assert result.theme == "dark"
        assert result.agent_verbose is True
        assert result.sidebar_collapsed is True
        assert result.notifications_enabled is False
        assert result.default_model_id == "gpt-4o"

    async def test_update_user_settings_upsert(self, repo):
        """Calling update twice should overwrite, not duplicate."""
        first = UserSettings(theme="dark")
        await repo.update_user_settings("user-1", first)

        second = UserSettings(theme="light", agent_verbose=True)
        await repo.update_user_settings("user-1", second)

        result = await repo.get_user_settings("user-1")
        assert result.theme == "light"
        assert result.agent_verbose is True

    async def test_different_users_have_separate_settings(self, repo):
        """Each user should have their own settings."""
        await repo.update_user_settings("user-1", UserSettings(theme="dark"))
        await repo.update_user_settings("user-2", UserSettings(theme="light"))

        r1 = await repo.get_user_settings("user-1")
        r2 = await repo.get_user_settings("user-2")
        assert r1.theme == "dark"
        assert r2.theme == "light"


class TestAppSettings:
    async def test_set_and_get_app_setting(self, repo):
        """A setting can be stored and retrieved by key."""
        await repo.set_app_setting("app_title", "My Desk")
        result = await repo.get_app_setting("app_title")
        assert result == "My Desk"

    async def test_get_app_setting_not_found(self, repo):
        """Missing keys should return None."""
        result = await repo.get_app_setting("nonexistent")
        assert result is None

    async def test_set_app_setting_upsert(self, repo):
        """Calling set twice should overwrite."""
        await repo.set_app_setting("accent", "#FF0000")
        await repo.set_app_setting("accent", "#00FF00")
        result = await repo.get_app_setting("accent")
        assert result == "#00FF00"

    async def test_get_all_app_settings(self, repo):
        """All settings should be returned."""
        await repo.set_app_setting("title", "Desk", category="general")
        await repo.set_app_setting("color", "#FFF", category="appearance")

        result = await repo.get_all_app_settings()
        assert result == {"title": "Desk", "color": "#FFF"}

    async def test_get_all_app_settings_by_category(self, repo):
        """Filtering by category should return only matching settings."""
        await repo.set_app_setting("title", "Desk", category="general")
        await repo.set_app_setting("color", "#FFF", category="appearance")
        await repo.set_app_setting("accent", "#000", category="appearance")

        result = await repo.get_all_app_settings(category="appearance")
        assert result == {"color": "#FFF", "accent": "#000"}

        general = await repo.get_all_app_settings(category="general")
        assert general == {"title": "Desk"}
