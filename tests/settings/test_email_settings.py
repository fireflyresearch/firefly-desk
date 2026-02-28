# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for email settings persistence."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.models.base import Base
from flydesk.settings.models import EmailSettings
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


class TestEmailSettings:
    async def test_get_defaults(self, repo):
        """When no email settings are saved, defaults should be returned."""
        settings = await repo.get_email_settings()
        assert isinstance(settings, EmailSettings)
        assert settings.enabled is False
        assert settings.provider == "resend"

    async def test_set_and_get(self, repo):
        """Saved email settings should be returned on subsequent reads."""
        settings = EmailSettings(
            enabled=True,
            from_address="ember@flydesk.ai",
            from_display_name="Ember AI",
            provider="resend",
        )
        await repo.set_email_settings(settings)
        result = await repo.get_email_settings()
        assert result.enabled is True
        assert result.from_address == "ember@flydesk.ai"
        assert result.from_display_name == "Ember AI"
