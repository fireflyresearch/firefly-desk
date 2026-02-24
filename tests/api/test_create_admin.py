# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for the POST /api/setup/create-admin endpoint."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.api.setup import router as setup_router
from flydesk.models.base import Base


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_app_with_db() -> FastAPI:
    """Create a FastAPI app backed by an in-memory SQLite database."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)

    # Import all models so Base.metadata knows about every table
    import flydesk.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    app = FastAPI()
    app.include_router(setup_router)
    app.state.session_factory = session_factory
    # Store engine for cleanup if needed
    app.state._engine = engine
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_admin_success():
    app = await _make_app_with_db()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/setup/create-admin",
            json={
                "username": "admin",
                "email": "admin@example.com",
                "display_name": "Admin User",
                "password": "securepass123",
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "user_id" in data

    await app.state._engine.dispose()


@pytest.mark.asyncio
async def test_create_admin_short_password():
    app = await _make_app_with_db()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/setup/create-admin",
            json={
                "username": "admin",
                "email": "admin@example.com",
                "display_name": "Admin",
                "password": "short",
            },
        )

    assert resp.status_code == 422
    assert "at least 8 characters" in resp.json()["detail"]

    await app.state._engine.dispose()


@pytest.mark.asyncio
async def test_create_admin_duplicate():
    """Second call should fail with 409 because an admin already exists."""
    app = await _make_app_with_db()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # First creation succeeds
        resp1 = await client.post(
            "/api/setup/create-admin",
            json={
                "username": "admin",
                "email": "admin@example.com",
                "display_name": "Admin",
                "password": "securepass123",
            },
        )
        assert resp1.status_code == 200

        # Second creation must fail
        resp2 = await client.post(
            "/api/setup/create-admin",
            json={
                "username": "admin2",
                "email": "admin2@example.com",
                "display_name": "Admin 2",
                "password": "securepass456",
            },
        )

    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"]

    await app.state._engine.dispose()


@pytest.mark.asyncio
async def test_create_admin_after_setup_completed():
    """Should fail with 403 when setup is already marked complete."""
    app = await _make_app_with_db()
    session_factory = app.state.session_factory

    # Mark setup as completed
    from flydesk.settings.repository import SettingsRepository

    settings_repo = SettingsRepository(session_factory)
    await settings_repo.set_app_setting("setup_completed", "true", category="setup")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/setup/create-admin",
            json={
                "username": "admin",
                "email": "admin@example.com",
                "display_name": "Admin",
                "password": "securepass123",
            },
        )

    assert resp.status_code == 403
    assert "Setup already completed" in resp.json()["detail"]

    await app.state._engine.dispose()


@pytest.mark.asyncio
async def test_create_admin_no_database():
    """Should fail with 500 when session_factory is not on app.state."""
    app = FastAPI()
    app.include_router(setup_router)
    # Deliberately do NOT set app.state.session_factory

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/setup/create-admin",
            json={
                "username": "admin",
                "email": "admin@example.com",
                "display_name": "Admin",
                "password": "securepass123",
            },
        )

    assert resp.status_code == 500
    assert "Database not initialized" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_created_admin_has_hashed_password():
    """The stored password should be a bcrypt hash, not plaintext."""
    app = await _make_app_with_db()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/setup/create-admin",
            json={
                "username": "admin",
                "email": "admin@example.com",
                "display_name": "Admin",
                "password": "securepass123",
            },
        )
    assert resp.status_code == 200

    # Verify the stored hash
    from flydesk.auth.local_user_repository import LocalUserRepository
    from flydesk.auth.password import verify_password

    repo = LocalUserRepository(app.state.session_factory)
    user = await repo.get_by_username("admin")
    assert user is not None
    assert user.role == "admin"
    assert user.password_hash != "securepass123"
    assert verify_password("securepass123", user.password_hash)

    await app.state._engine.dispose()
