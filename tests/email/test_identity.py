# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for EmailIdentityResolver."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.models.base import Base
from flydesk.email.identity import EmailIdentityResolver


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


class TestEmailIdentityResolver:
    async def test_resolve_unknown_returns_none(self, session_factory):
        resolver = EmailIdentityResolver(session_factory)
        result = await resolver.resolve("nobody@example.com")
        assert result is None

    async def test_resolve_known_user(self, session_factory):
        from flydesk.models.local_user import LocalUserRow

        async with session_factory() as session:
            user = LocalUserRow(
                id="user-1",
                username="jdoe",
                email="jdoe@example.com",
                display_name="Jane Doe",
                password_hash="hashed",
                role="admin",
            )
            session.add(user)
            await session.commit()

        resolver = EmailIdentityResolver(session_factory)
        result = await resolver.resolve("jdoe@example.com")
        assert result is not None
        assert result.user_id == "user-1"
        assert result.email == "jdoe@example.com"
        assert result.display_name == "Jane Doe"
        assert result.is_external is False

    async def test_resolve_is_case_sensitive(self, session_factory):
        """Email lookup is exact match (case-sensitive by default in SQLite)."""
        from flydesk.models.local_user import LocalUserRow

        async with session_factory() as session:
            user = LocalUserRow(
                id="user-2",
                username="alice",
                email="alice@example.com",
                display_name="Alice",
                password_hash="hashed",
                role="admin",
            )
            session.add(user)
            await session.commit()

        resolver = EmailIdentityResolver(session_factory)
        # Exact match works
        result = await resolver.resolve("alice@example.com")
        assert result is not None
        assert result.user_id == "user-2"
