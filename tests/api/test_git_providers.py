# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the Git Providers Admin REST API."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from flydesk.auth.models import UserSession
from flydesk.knowledge.git_provider_repository import GitProviderRepository
from flydesk.models.base import Base
from flydesk.models.git_provider import GitProviderRow


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_user_session(*, roles: list[str] | None = None) -> UserSession:
    """Build a UserSession for testing."""
    return UserSession(
        user_id="user-1",
        email="admin@example.com",
        display_name="Admin User",
        roles=roles or [],
        permissions=["*"] if "admin" in (roles or []) else [],
        tenant_id="tenant-1",
        session_id="sess-1",
        token_expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        raw_claims={},
    )


def _sample_row(provider_id: str = "prov-1", **overrides) -> GitProviderRow:
    """Build a sample GitProviderRow for mocked responses."""
    defaults = dict(
        id=provider_id,
        provider_type="github",
        display_name="GitHub Cloud",
        base_url="https://api.github.com",
        auth_method="oauth",
        client_id="gh-client-id",
        client_secret_encrypted="encrypted-secret",
        oauth_authorize_url="https://github.com/login/oauth/authorize",
        oauth_token_url="https://github.com/login/oauth/access_token",
        scopes='["repo", "read:org"]',
        is_active=True,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return GitProviderRow(**defaults)


@pytest.fixture
def mock_repo():
    """Return an AsyncMock that mimics GitProviderRepository."""
    repo = AsyncMock()
    repo.create_provider = AsyncMock(return_value=None)
    repo.get_provider = AsyncMock(return_value=None)
    repo.list_providers = AsyncMock(return_value=[])
    repo.update_provider = AsyncMock(return_value=None)
    repo.delete_provider = AsyncMock(return_value=None)
    repo.decrypt_secret = MagicMock(return_value="decrypted-secret")
    return repo


@pytest.fixture
async def admin_client(mock_repo):
    """AsyncClient with an admin user session and mocked GitProviderRepository."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.git_providers import get_git_provider_repo
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_git_provider_repo] = lambda: mock_repo

        # Inject admin user_session into request state via middleware
        admin_session = _make_user_session(roles=["admin"])

        async def _set_user(request, call_next):
            request.state.user_session = admin_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture
async def non_admin_client(mock_repo):
    """AsyncClient with a non-admin user session."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.git_providers import get_git_provider_repo
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_git_provider_repo] = lambda: mock_repo

        viewer_session = _make_user_session(roles=["viewer"])

        async def _set_user(request, call_next):
            request.state.user_session = viewer_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture
async def db_session_factory():
    """Create a real SQLite-backed async session factory for repository tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def real_repo(db_session_factory):
    """GitProviderRepository backed by a real SQLite database."""
    return GitProviderRepository(db_session_factory)


# ---------------------------------------------------------------------------
# Repository Tests (real SQLite)
# ---------------------------------------------------------------------------


class TestGitProviderRepository:
    async def test_create_and_get_provider(self, real_repo):
        row = await real_repo.create_provider(
            provider_type="github",
            display_name="GitHub Cloud",
            base_url="https://api.github.com",
            client_id="gh-client-id",
            client_secret="super-secret",
            oauth_authorize_url="https://github.com/login/oauth/authorize",
            oauth_token_url="https://github.com/login/oauth/access_token",
            scopes=["repo", "read:org"],
            is_active=True,
        )
        assert row.id is not None
        assert row.provider_type == "github"
        assert row.display_name == "GitHub Cloud"
        assert row.client_secret_encrypted is not None
        assert row.client_secret_encrypted != "super-secret"

        fetched = await real_repo.get_provider(row.id)
        assert fetched is not None
        assert fetched.id == row.id
        assert fetched.base_url == "https://api.github.com"

    async def test_list_providers(self, real_repo):
        await real_repo.create_provider(
            provider_type="github",
            display_name="GitHub",
            base_url="https://api.github.com",
            client_id="id1",
        )
        await real_repo.create_provider(
            provider_type="gitlab",
            display_name="GitLab",
            base_url="https://gitlab.com/api/v4",
            client_id="id2",
        )
        providers = await real_repo.list_providers()
        assert len(providers) == 2
        # Ordered by display_name
        assert providers[0].display_name == "GitHub"
        assert providers[1].display_name == "GitLab"

    async def test_update_provider(self, real_repo):
        row = await real_repo.create_provider(
            provider_type="github",
            display_name="Old Name",
            base_url="https://api.github.com",
            client_id="id1",
        )
        updated = await real_repo.update_provider(
            row.id,
            display_name="New Name",
            base_url="https://github.example.com/api",
        )
        assert updated is not None
        assert updated.display_name == "New Name"
        assert updated.base_url == "https://github.example.com/api"

    async def test_update_provider_secret(self, real_repo):
        row = await real_repo.create_provider(
            provider_type="github",
            display_name="GitHub",
            base_url="https://api.github.com",
            client_id="id1",
            client_secret="old-secret",
        )
        old_encrypted = row.client_secret_encrypted
        updated = await real_repo.update_provider(
            row.id,
            client_secret="new-secret",
        )
        assert updated is not None
        assert updated.client_secret_encrypted != old_encrypted

    async def test_update_provider_not_found(self, real_repo):
        result = await real_repo.update_provider("nonexistent-id", display_name="X")
        assert result is None

    async def test_delete_provider(self, real_repo):
        row = await real_repo.create_provider(
            provider_type="github",
            display_name="To Delete",
            base_url="https://api.github.com",
            client_id="id1",
        )
        await real_repo.delete_provider(row.id)
        assert await real_repo.get_provider(row.id) is None

    async def test_encrypt_decrypt_secret(self, real_repo):
        row = await real_repo.create_provider(
            provider_type="github",
            display_name="GitHub",
            base_url="https://api.github.com",
            client_id="id1",
            client_secret="my-secret-value",
        )
        decrypted = real_repo.decrypt_secret(row)
        assert decrypted == "my-secret-value"

    async def test_decrypt_none_secret(self, real_repo):
        row = await real_repo.create_provider(
            provider_type="github",
            display_name="GitHub",
            base_url="https://api.github.com",
            client_id="id1",
        )
        assert real_repo.decrypt_secret(row) is None

    async def test_parse_scopes(self, real_repo):
        row = await real_repo.create_provider(
            provider_type="github",
            display_name="GitHub",
            base_url="https://api.github.com",
            client_id="id1",
            scopes=["repo", "read:org"],
        )
        scopes = real_repo.parse_scopes(row)
        assert scopes == ["repo", "read:org"]

    async def test_parse_scopes_none(self, real_repo):
        row = await real_repo.create_provider(
            provider_type="github",
            display_name="GitHub",
            base_url="https://api.github.com",
            client_id="id1",
        )
        scopes = real_repo.parse_scopes(row)
        assert scopes == []

    async def test_update_scopes(self, real_repo):
        row = await real_repo.create_provider(
            provider_type="github",
            display_name="GitHub",
            base_url="https://api.github.com",
            client_id="id1",
            scopes=["repo"],
        )
        updated = await real_repo.update_provider(
            row.id,
            scopes=["repo", "read:org", "user"],
        )
        assert updated is not None
        scopes = real_repo.parse_scopes(updated)
        assert scopes == ["repo", "read:org", "user"]


# ---------------------------------------------------------------------------
# CRUD API Tests
# ---------------------------------------------------------------------------


class TestListProviders:
    async def test_list_providers_empty(self, admin_client, mock_repo):
        mock_repo.list_providers.return_value = []
        response = await admin_client.get("/api/admin/git-providers")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_providers_returns_items(self, admin_client, mock_repo):
        mock_repo.list_providers.return_value = [_sample_row()]
        response = await admin_client.get("/api/admin/git-providers")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "prov-1"
        assert data[0]["display_name"] == "GitHub Cloud"

    async def test_list_providers_hides_secret(self, admin_client, mock_repo):
        mock_repo.list_providers.return_value = [_sample_row()]
        response = await admin_client.get("/api/admin/git-providers")
        data = response.json()
        assert "client_secret" not in data[0]
        assert "client_secret_encrypted" not in data[0]
        assert data[0]["has_client_secret"] is True


class TestCreateProvider:
    async def test_create_provider(self, admin_client, mock_repo):
        created_row = _sample_row()
        mock_repo.create_provider.return_value = created_row
        body = {
            "provider_type": "github",
            "display_name": "GitHub Cloud",
            "base_url": "https://api.github.com",
            "client_id": "gh-client-id",
            "client_secret": "my-secret",
            "oauth_authorize_url": "https://github.com/login/oauth/authorize",
            "oauth_token_url": "https://github.com/login/oauth/access_token",
            "scopes": ["repo", "read:org"],
        }
        response = await admin_client.post("/api/admin/git-providers", json=body)
        assert response.status_code == 201
        mock_repo.create_provider.assert_awaited_once()
        data = response.json()
        assert data["id"] == "prov-1"
        assert data["has_client_secret"] is True

    async def test_create_provider_strips_secret(self, admin_client, mock_repo):
        created_row = _sample_row()
        mock_repo.create_provider.return_value = created_row
        body = {
            "provider_type": "github",
            "display_name": "GitHub Cloud",
            "base_url": "https://api.github.com",
            "client_id": "gh-client-id",
            "client_secret": "my-secret",
        }
        response = await admin_client.post("/api/admin/git-providers", json=body)
        data = response.json()
        assert "client_secret" not in data
        assert "client_secret_encrypted" not in data


class TestGetProvider:
    async def test_get_provider(self, admin_client, mock_repo):
        mock_repo.get_provider.return_value = _sample_row()
        response = await admin_client.get("/api/admin/git-providers/prov-1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "prov-1"
        assert data["provider_type"] == "github"
        assert "client_secret" not in data
        assert data["has_client_secret"] is True

    async def test_get_provider_not_found(self, admin_client, mock_repo):
        mock_repo.get_provider.return_value = None
        response = await admin_client.get("/api/admin/git-providers/no-such")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestUpdateProvider:
    async def test_update_provider(self, admin_client, mock_repo):
        original = _sample_row()
        updated = _sample_row()
        updated.display_name = "Updated Name"
        mock_repo.get_provider.return_value = original
        mock_repo.update_provider.return_value = updated
        body = {
            "provider_type": "github",
            "display_name": "Updated Name",
            "base_url": "https://api.github.com",
            "client_id": "gh-client-id",
        }
        response = await admin_client.put("/api/admin/git-providers/prov-1", json=body)
        assert response.status_code == 200
        mock_repo.update_provider.assert_awaited_once()

    async def test_update_provider_not_found(self, admin_client, mock_repo):
        mock_repo.get_provider.return_value = None
        body = {
            "provider_type": "github",
            "display_name": "X",
            "base_url": "https://api.github.com",
            "client_id": "id1",
        }
        response = await admin_client.put("/api/admin/git-providers/prov-1", json=body)
        assert response.status_code == 404


class TestDeleteProvider:
    async def test_delete_provider(self, admin_client, mock_repo):
        mock_repo.get_provider.return_value = _sample_row()
        response = await admin_client.delete("/api/admin/git-providers/prov-1")
        assert response.status_code == 204
        mock_repo.delete_provider.assert_awaited_once_with("prov-1")

    async def test_delete_provider_not_found(self, admin_client, mock_repo):
        mock_repo.get_provider.return_value = None
        response = await admin_client.delete("/api/admin/git-providers/no-such")
        assert response.status_code == 404


class TestTestProvider:
    async def test_test_provider_not_found(self, admin_client, mock_repo):
        mock_repo.get_provider.return_value = None
        response = await admin_client.post("/api/admin/git-providers/no-such/test")
        assert response.status_code == 404

    async def test_test_provider_success(self, admin_client, mock_repo):
        mock_repo.get_provider.return_value = _sample_row()

        mock_provider = AsyncMock()
        mock_provider.validate_token.return_value = True
        mock_provider.aclose = AsyncMock()

        with patch(
            "flydesk.knowledge.git_provider.GitProviderFactory"
        ) as mock_factory:
            mock_factory.create.return_value = mock_provider
            response = await admin_client.post("/api/admin/git-providers/prov-1/test")

        assert response.status_code == 200
        data = response.json()
        assert data["reachable"] is True
        assert data["provider_type"] == "github"

    async def test_test_provider_failure(self, admin_client, mock_repo):
        mock_repo.get_provider.return_value = _sample_row()

        with patch(
            "flydesk.knowledge.git_provider.GitProviderFactory"
        ) as mock_factory:
            mock_factory.create.side_effect = ValueError("Unsupported provider")
            response = await admin_client.post("/api/admin/git-providers/prov-1/test")

        assert response.status_code == 200
        data = response.json()
        assert data["reachable"] is False
        assert "Unsupported provider" in data["error"]


# ---------------------------------------------------------------------------
# Admin guard
# ---------------------------------------------------------------------------


class TestAdminGuard:
    async def test_non_admin_cannot_list_providers(self, non_admin_client):
        response = await non_admin_client.get("/api/admin/git-providers")
        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    async def test_non_admin_cannot_create_provider(self, non_admin_client):
        body = {
            "provider_type": "github",
            "display_name": "GitHub",
            "base_url": "https://api.github.com",
            "client_id": "id1",
        }
        response = await non_admin_client.post("/api/admin/git-providers", json=body)
        assert response.status_code == 403

    async def test_non_admin_cannot_delete_provider(self, non_admin_client):
        response = await non_admin_client.delete("/api/admin/git-providers/prov-1")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# PAT support
# ---------------------------------------------------------------------------


class TestPATSupport:
    """Tests for Personal Access Token authentication method."""

    async def test_create_pat_provider(self, admin_client, mock_repo):
        created_row = _sample_row(auth_method="pat", client_id=None)
        mock_repo.create_provider.return_value = created_row
        body = {
            "provider_type": "github",
            "display_name": "GitHub PAT",
            "base_url": "https://api.github.com",
            "auth_method": "pat",
            "client_secret": "ghp_mytoken123",
        }
        response = await admin_client.post("/api/admin/git-providers", json=body)
        assert response.status_code == 201
        data = response.json()
        assert data["auth_method"] == "pat"
        assert data["has_client_secret"] is True

    async def test_create_pat_provider_no_client_id(self, admin_client, mock_repo):
        """PAT providers do not require client_id."""
        created_row = _sample_row(auth_method="pat", client_id=None)
        mock_repo.create_provider.return_value = created_row
        body = {
            "provider_type": "github",
            "display_name": "GitHub PAT",
            "base_url": "https://api.github.com",
            "auth_method": "pat",
            "client_secret": "ghp_mytoken123",
        }
        response = await admin_client.post("/api/admin/git-providers", json=body)
        assert response.status_code == 201
        data = response.json()
        assert data["client_id"] is None

    async def test_response_includes_auth_method(self, admin_client, mock_repo):
        mock_repo.list_providers.return_value = [
            _sample_row("prov-1", auth_method="oauth"),
            _sample_row("prov-2", auth_method="pat", client_id=None),
        ]
        response = await admin_client.get("/api/admin/git-providers")
        data = response.json()
        assert data[0]["auth_method"] == "oauth"
        assert data[1]["auth_method"] == "pat"

    async def test_repo_create_with_auth_method(self, real_repo):
        """Repository persists auth_method correctly."""
        row = await real_repo.create_provider(
            provider_type="github",
            display_name="GitHub PAT",
            base_url="https://api.github.com",
            auth_method="pat",
            client_secret="ghp_token",
        )
        assert row.auth_method == "pat"
        assert row.client_id is None
        decrypted = real_repo.decrypt_secret(row)
        assert decrypted == "ghp_token"

    async def test_repo_update_auth_method(self, real_repo):
        """Can switch a provider from oauth to pat."""
        row = await real_repo.create_provider(
            provider_type="github",
            display_name="GitHub",
            base_url="https://api.github.com",
            auth_method="oauth",
            client_id="gh-client",
        )
        assert row.auth_method == "oauth"
        updated = await real_repo.update_provider(
            row.id,
            auth_method="pat",
            client_id=None,
            client_secret="ghp_new_token",
        )
        assert updated is not None
        assert updated.auth_method == "pat"
        assert updated.client_id is None
