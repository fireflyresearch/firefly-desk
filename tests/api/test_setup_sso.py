# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for SSO, FQDN, and locale setup wizard endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

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
    app.state._engine = engine
    return app


async def _mark_setup_completed(app: FastAPI) -> None:
    """Mark setup as completed in the database."""
    from flydesk.settings.repository import SettingsRepository

    settings_repo = SettingsRepository(app.state.session_factory)
    await settings_repo.set_app_setting("setup_completed", "true", category="setup")


# ---------------------------------------------------------------------------
# POST /api/setup/configure-sso
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_configure_sso_success():
    app = await _make_app_with_db()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/setup/configure-sso",
            json={
                "provider_type": "entra_id",
                "display_name": "Corporate SSO",
                "issuer_url": "https://login.microsoftonline.com/tenant-id/v2.0",
                "client_id": "test-client-id",
                "client_secret": "test-secret",
                "tenant_id": "tenant-id",
                "scopes": ["openid", "profile", "email"],
                "allowed_email_domains": ["example.com"],
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "provider_id" in data

    # Verify provider was persisted
    from flydesk.auth.repository import OIDCProviderRepository

    oidc_repo = OIDCProviderRepository(app.state.session_factory)
    provider = await oidc_repo.get_provider(data["provider_id"])
    assert provider is not None
    assert provider.provider_type == "entra_id"
    assert provider.display_name == "Corporate SSO"
    assert provider.is_active is True

    await app.state._engine.dispose()


@pytest.mark.asyncio
async def test_configure_sso_blocked_after_setup_completed():
    app = await _make_app_with_db()
    await _mark_setup_completed(app)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/setup/configure-sso",
            json={
                "provider_type": "entra_id",
                "display_name": "Corporate SSO",
                "issuer_url": "https://login.microsoftonline.com/tenant/v2.0",
                "client_id": "test-client-id",
            },
        )

    assert resp.status_code == 403
    assert "Setup already completed" in resp.json()["detail"]

    await app.state._engine.dispose()


@pytest.mark.asyncio
async def test_configure_sso_no_database():
    app = FastAPI()
    app.include_router(setup_router)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/setup/configure-sso",
            json={
                "provider_type": "entra_id",
                "display_name": "Corporate SSO",
                "issuer_url": "https://login.microsoftonline.com/tenant/v2.0",
                "client_id": "test-client-id",
            },
        )

    assert resp.status_code == 500
    assert "Database not initialized" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# POST /api/setup/test-sso
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_test_sso_success():
    """Test SSO connectivity endpoint with mocked OIDC discovery."""
    app = await _make_app_with_db()

    from flydesk.auth.oidc import OIDCDiscoveryDocument

    mock_discovery = OIDCDiscoveryDocument(
        issuer="https://idp.example.com",
        authorization_endpoint="https://idp.example.com/authorize",
        token_endpoint="https://idp.example.com/token",
        jwks_uri="https://idp.example.com/.well-known/jwks.json",
        userinfo_endpoint="https://idp.example.com/userinfo",
    )

    with patch(
        "flydesk.auth.oidc.OIDCClient.discover",
        new_callable=AsyncMock,
        return_value=mock_discovery,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/setup/test-sso",
                json={"issuer_url": "https://idp.example.com"},
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["reachable"] is True
    assert data["issuer"] == "https://idp.example.com"
    assert data["authorization_endpoint"] == "https://idp.example.com/authorize"
    assert data["token_endpoint"] == "https://idp.example.com/token"

    await app.state._engine.dispose()


@pytest.mark.asyncio
async def test_test_sso_failure():
    """Test SSO connectivity when discovery fails."""
    app = await _make_app_with_db()

    with patch(
        "flydesk.auth.oidc.OIDCClient.discover",
        new_callable=AsyncMock,
        side_effect=Exception("Connection refused"),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/setup/test-sso",
                json={"issuer_url": "https://bad-issuer.example.com"},
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["reachable"] is False
    assert "Connection refused" in data["error"]

    await app.state._engine.dispose()


@pytest.mark.asyncio
async def test_test_sso_blocked_after_setup_completed():
    app = await _make_app_with_db()
    await _mark_setup_completed(app)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/setup/test-sso",
            json={"issuer_url": "https://idp.example.com"},
        )

    assert resp.status_code == 403
    assert "Setup already completed" in resp.json()["detail"]

    await app.state._engine.dispose()


# ---------------------------------------------------------------------------
# POST /api/setup/configure-fqdn
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_configure_fqdn_success():
    app = await _make_app_with_db()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/setup/configure-fqdn",
            json={"fqdn": "myapp.example.com", "protocol": "https"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["base_url"] == "https://myapp.example.com"

    # Verify settings were persisted
    from flydesk.settings.repository import SettingsRepository

    settings_repo = SettingsRepository(app.state.session_factory)
    assert await settings_repo.get_app_setting("fqdn") == "myapp.example.com"
    assert await settings_repo.get_app_setting("protocol") == "https"

    await app.state._engine.dispose()


@pytest.mark.asyncio
async def test_configure_fqdn_localhost():
    app = await _make_app_with_db()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/setup/configure-fqdn",
            json={"fqdn": "localhost:5173", "protocol": "http"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["base_url"] == "http://localhost:5173"

    await app.state._engine.dispose()


@pytest.mark.asyncio
async def test_configure_fqdn_blocked_after_setup_completed():
    app = await _make_app_with_db()
    await _mark_setup_completed(app)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/setup/configure-fqdn",
            json={"fqdn": "myapp.example.com"},
        )

    assert resp.status_code == 403
    assert "Setup already completed" in resp.json()["detail"]

    await app.state._engine.dispose()


# ---------------------------------------------------------------------------
# POST /api/setup/configure-locale
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_configure_locale_success():
    app = await _make_app_with_db()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/setup/configure-locale",
            json={
                "language": "en-US",
                "timezone": "America/New_York",
                "country": "US",
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True

    # Verify settings were persisted
    from flydesk.settings.repository import SettingsRepository

    settings_repo = SettingsRepository(app.state.session_factory)
    assert await settings_repo.get_app_setting("locale_language") == "en-US"
    assert await settings_repo.get_app_setting("locale_timezone") == "America/New_York"
    assert await settings_repo.get_app_setting("locale_country") == "US"

    await app.state._engine.dispose()


@pytest.mark.asyncio
async def test_configure_locale_without_country():
    app = await _make_app_with_db()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/setup/configure-locale",
            json={
                "language": "fr-FR",
                "timezone": "Europe/Paris",
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True

    # Verify settings were persisted - country should not be set
    from flydesk.settings.repository import SettingsRepository

    settings_repo = SettingsRepository(app.state.session_factory)
    assert await settings_repo.get_app_setting("locale_language") == "fr-FR"
    assert await settings_repo.get_app_setting("locale_timezone") == "Europe/Paris"
    assert await settings_repo.get_app_setting("locale_country") is None

    await app.state._engine.dispose()


@pytest.mark.asyncio
async def test_configure_locale_blocked_after_setup_completed():
    app = await _make_app_with_db()
    await _mark_setup_completed(app)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/setup/configure-locale",
            json={"language": "en-US", "timezone": "America/New_York"},
        )

    assert resp.status_code == 403
    assert "Setup already completed" in resp.json()["detail"]

    await app.state._engine.dispose()


# ---------------------------------------------------------------------------
# GET /api/setup/status -- new fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_setup_status_includes_new_fields():
    """SetupStatus should include has_sso_configured, fqdn, and locale_language."""
    app = await _make_app_with_db()

    # Configure FQDN and locale via the setup endpoints
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Set FQDN
        await client.post(
            "/api/setup/configure-fqdn",
            json={"fqdn": "app.example.com", "protocol": "https"},
        )
        # Set locale
        await client.post(
            "/api/setup/configure-locale",
            json={"language": "en-US", "timezone": "America/New_York"},
        )

        # Check status
        resp = await client.get("/api/setup/status")

    assert resp.status_code == 200
    data = resp.json()

    # New fields should be present
    assert "has_sso_configured" in data
    assert data["has_sso_configured"] is False  # No SSO configured yet
    assert data["fqdn"] == "app.example.com"
    assert data["locale_language"] == "en-US"

    await app.state._engine.dispose()


@pytest.mark.asyncio
async def test_setup_status_with_sso_configured():
    """SetupStatus.has_sso_configured should be True after configuring SSO."""
    app = await _make_app_with_db()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Configure SSO
        await client.post(
            "/api/setup/configure-sso",
            json={
                "provider_type": "keycloak",
                "display_name": "Test IdP",
                "issuer_url": "https://idp.example.com/realms/test",
                "client_id": "flydesk",
            },
        )

        # Check status
        resp = await client.get("/api/setup/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["has_sso_configured"] is True

    await app.state._engine.dispose()


@pytest.mark.asyncio
async def test_setup_status_defaults_when_nothing_configured():
    """New fields should default to empty/false when nothing is configured."""
    app = await _make_app_with_db()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/setup/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["has_sso_configured"] is False
    assert data["fqdn"] == ""
    assert data["locale_language"] == ""

    await app.state._engine.dispose()
