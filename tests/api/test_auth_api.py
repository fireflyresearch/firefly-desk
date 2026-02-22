# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for the Auth API endpoints (login-url, callback, logout, providers)."""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydek.auth.oidc import OIDCClient, OIDCDiscoveryDocument
from flydek.auth.repository import OIDCProviderRepository
from flydek.models.base import Base

ISSUER = "https://idp.example.com"
DISCOVERY_DOC = OIDCDiscoveryDocument(
    issuer=ISSUER,
    authorization_endpoint=f"{ISSUER}/protocol/openid-connect/auth",
    token_endpoint=f"{ISSUER}/protocol/openid-connect/token",
    jwks_uri=f"{ISSUER}/protocol/openid-connect/certs",
    userinfo_endpoint=f"{ISSUER}/protocol/openid-connect/userinfo",
    end_session_endpoint=f"{ISSUER}/protocol/openid-connect/logout",
)


@pytest.fixture
async def _auth_fixtures():
    """Set up an in-memory DB with a seeded OIDC provider, and yield (repo, encryption_key)."""
    encryption_key = Fernet.generate_key().decode()

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    repo = OIDCProviderRepository(session_factory, encryption_key)

    # Seed one active provider
    await repo.create_provider(
        provider_type="keycloak",
        display_name="Test Keycloak",
        issuer_url=ISSUER,
        client_id="test-client",
        client_secret="test-secret",
        scopes=["openid", "profile", "email"],
        is_active=True,
    )

    yield repo, encryption_key
    await engine.dispose()


@pytest.fixture
async def client(_auth_fixtures):
    """AsyncClient wired to the full Firefly Desk app with auth dependency overrides."""
    repo, encryption_key = _auth_fixtures

    env = {
        "FLYDEK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDEK_DEV_MODE": "true",
        "FLYDEK_OIDC_ISSUER_URL": ISSUER,
        "FLYDEK_OIDC_CLIENT_ID": "test-client",
        "FLYDEK_OIDC_CLIENT_SECRET": "test-secret",
        "FLYDEK_CREDENTIAL_ENCRYPTION_KEY": encryption_key,
    }
    with patch.dict(os.environ, env):
        from flydek.api.auth import get_oidc_client, get_oidc_repo
        from flydek.server import create_app

        app = create_app()

        # Override OIDC dependency with our seeded repo
        app.dependency_overrides[get_oidc_repo] = lambda: repo

        # Provide a default OIDCClient for logout/userinfo
        oidc_client = OIDCClient(
            issuer_url=ISSUER,
            client_id="test-client",
            client_secret="test-secret",
        )
        app.dependency_overrides[get_oidc_client] = lambda: oidc_client

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


class TestListProviders:
    async def test_list_providers_returns_active(self, client: AsyncClient):
        """GET /api/auth/providers returns active providers."""
        response = await client.get("/api/auth/providers")
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        assert len(body) >= 1
        provider = body[0]
        assert provider["provider_type"] == "keycloak"
        assert provider["display_name"] == "Test Keycloak"
        assert provider["issuer_url"] == ISSUER
        assert "id" in provider


class TestLoginUrl:
    async def test_get_login_url(self, client: AsyncClient, _auth_fixtures):
        """GET /api/auth/login-url returns a login URL and state."""
        repo, _ = _auth_fixtures
        providers = await repo.list_providers()
        provider_id = providers[0].id

        # Mock the OIDC discover() call that login-url makes
        with patch.object(
            OIDCClient,
            "discover",
            new_callable=AsyncMock,
            return_value=DISCOVERY_DOC,
        ):
            response = await client.get(
                "/api/auth/login-url",
                params={
                    "provider_id": provider_id,
                    "redirect_uri": "http://localhost:3000/callback",
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert "login_url" in body
        assert "state" in body
        assert body["login_url"].startswith(DISCOVERY_DOC.authorization_endpoint)
        assert "response_type=code" in body["login_url"]

    async def test_get_login_url_unknown_provider(self, client: AsyncClient):
        """GET /api/auth/login-url with an unknown provider_id returns 404."""
        response = await client.get(
            "/api/auth/login-url",
            params={"provider_id": "nonexistent-id"},
        )
        assert response.status_code == 404


class TestCallback:
    async def test_callback_missing_code_returns_400(self, client: AsyncClient):
        """POST /api/auth/callback without code or state returns 400."""
        response = await client.post("/api/auth/callback", json={"code": "", "state": ""})
        assert response.status_code == 400
        assert "Missing code or state" in response.json()["detail"]

    async def test_callback_invalid_state_returns_400(self, client: AsyncClient):
        """POST /api/auth/callback with an unknown state returns 400."""
        response = await client.post(
            "/api/auth/callback",
            json={"code": "some-code", "state": "invalid-state"},
        )
        assert response.status_code == 400
        assert "Invalid or expired" in response.json()["detail"]


class TestLogout:
    async def test_logout_clears_cookie(self, client: AsyncClient):
        """POST /api/auth/logout returns status and clears the cookie."""
        # Mock discovery for the logout endpoint
        with patch.object(
            OIDCClient,
            "discover",
            new_callable=AsyncMock,
            return_value=DISCOVERY_DOC,
        ):
            response = await client.post("/api/auth/logout")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "logged_out"
        assert body["end_session_url"] == DISCOVERY_DOC.end_session_endpoint

        # The Set-Cookie header should delete flydek_token
        set_cookie = response.headers.get("set-cookie", "")
        assert "flydek_token" in set_cookie

    async def test_logout_without_oidc_client(self, client: AsyncClient):
        """POST /api/auth/logout works even without an OIDCClient."""
        from flydek.api.auth import get_oidc_client

        # Temporarily override to return None
        original = client._transport.app.dependency_overrides.get(get_oidc_client)  # type: ignore[attr-defined]
        client._transport.app.dependency_overrides[get_oidc_client] = lambda: None  # type: ignore[attr-defined]

        response = await client.post("/api/auth/logout")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "logged_out"
        assert "end_session_url" not in body

        # Restore
        if original is not None:
            client._transport.app.dependency_overrides[get_oidc_client] = original  # type: ignore[attr-defined]
