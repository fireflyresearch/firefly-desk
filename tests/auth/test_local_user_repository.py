# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for LocalUserRepository CRUD operations."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.auth.local_user_repository import LocalUserRepository
from flydesk.auth.password import hash_password
from flydesk.models.base import Base


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def repo(session_factory) -> LocalUserRepository:
    return LocalUserRepository(session_factory)


class TestLocalUserRepository:
    async def test_create_and_get_by_id(self, repo: LocalUserRepository):
        """Create a user and retrieve it by ID."""
        row = await repo.create_user(
            username="admin",
            email="admin@example.com",
            display_name="Admin User",
            password_hash=hash_password("secret123"),
        )
        assert row.id is not None
        assert row.username == "admin"
        assert row.email == "admin@example.com"
        assert row.display_name == "Admin User"
        assert row.role == "admin"
        assert row.is_active is True
        assert row.created_at is not None
        assert row.updated_at is not None

        fetched = await repo.get_by_id(row.id)
        assert fetched is not None
        assert fetched.username == "admin"

    async def test_create_with_custom_role(self, repo: LocalUserRepository):
        """create_user() respects a custom role."""
        row = await repo.create_user(
            username="viewer",
            email="viewer@example.com",
            display_name="Viewer User",
            password_hash=hash_password("pass"),
            role="viewer",
        )
        assert row.role == "viewer"

    async def test_get_by_username(self, repo: LocalUserRepository):
        """get_by_username() retrieves the correct user."""
        await repo.create_user(
            username="alice",
            email="alice@example.com",
            display_name="Alice",
            password_hash=hash_password("alice-pass"),
        )
        await repo.create_user(
            username="bob",
            email="bob@example.com",
            display_name="Bob",
            password_hash=hash_password("bob-pass"),
        )

        alice = await repo.get_by_username("alice")
        assert alice is not None
        assert alice.display_name == "Alice"

        bob = await repo.get_by_username("bob")
        assert bob is not None
        assert bob.display_name == "Bob"

    async def test_get_by_username_not_found(self, repo: LocalUserRepository):
        """get_by_username() returns None for a nonexistent username."""
        result = await repo.get_by_username("nonexistent")
        assert result is None

    async def test_get_by_id_not_found(self, repo: LocalUserRepository):
        """get_by_id() returns None for a nonexistent ID."""
        result = await repo.get_by_id("no-such-id")
        assert result is None

    async def test_has_any_user_empty(self, repo: LocalUserRepository):
        """has_any_user() returns False when there are no users."""
        assert await repo.has_any_user() is False

    async def test_has_any_user_with_users(self, repo: LocalUserRepository):
        """has_any_user() returns True after creating a user."""
        await repo.create_user(
            username="first",
            email="first@example.com",
            display_name="First",
            password_hash=hash_password("pass"),
        )
        assert await repo.has_any_user() is True

    async def test_count_users_empty(self, repo: LocalUserRepository):
        """count_users() returns 0 when there are no users."""
        assert await repo.count_users() == 0

    async def test_count_users(self, repo: LocalUserRepository):
        """count_users() returns the correct count."""
        await repo.create_user(
            username="user1",
            email="user1@example.com",
            display_name="User One",
            password_hash=hash_password("pass"),
        )
        await repo.create_user(
            username="user2",
            email="user2@example.com",
            display_name="User Two",
            password_hash=hash_password("pass"),
        )
        assert await repo.count_users() == 2

    async def test_get_by_email(self, repo: LocalUserRepository):
        """get_by_email() retrieves the correct user."""
        await repo.create_user(
            username="admin",
            email="admin@example.com",
            display_name="Admin",
            password_hash=hash_password("pass"),
        )
        result = await repo.get_by_email("admin@example.com")
        assert result is not None
        assert result.username == "admin"

    async def test_get_by_email_case_insensitive(self, repo: LocalUserRepository):
        """get_by_email() performs case-insensitive matching."""
        await repo.create_user(
            username="admin",
            email="Admin@Example.COM",
            display_name="Admin",
            password_hash=hash_password("pass"),
        )
        result = await repo.get_by_email("admin@example.com")
        assert result is not None
        assert result.username == "admin"

        result_upper = await repo.get_by_email("ADMIN@EXAMPLE.COM")
        assert result_upper is not None
        assert result_upper.username == "admin"

    async def test_get_by_email_not_found(self, repo: LocalUserRepository):
        """get_by_email() returns None for a nonexistent email."""
        result = await repo.get_by_email("nobody@example.com")
        assert result is None

    async def test_unique_username_constraint(self, repo: LocalUserRepository):
        """Creating two users with the same username raises an error."""
        await repo.create_user(
            username="duplicate",
            email="first@example.com",
            display_name="First",
            password_hash=hash_password("pass"),
        )
        with pytest.raises(Exception):  # noqa: B017
            await repo.create_user(
                username="duplicate",
                email="second@example.com",
                display_name="Second",
                password_hash=hash_password("pass"),
            )
