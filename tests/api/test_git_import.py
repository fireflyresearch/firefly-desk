# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the provider-agnostic Git import API."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from flydesk.auth.models import UserSession
from flydesk.knowledge.git_provider import (
    GitAccount,
    GitBranch,
    GitFileContent,
    GitRepo,
    GitTreeEntry,
)
from flydesk.models.git_provider import GitProviderRow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user_session(*, permissions: list[str] | None = None) -> UserSession:
    """Build a UserSession for testing."""
    return UserSession(
        user_id="user-1",
        email="admin@example.com",
        display_name="Admin User",
        roles=["admin"],
        permissions=permissions or ["*"],
        tenant_id="tenant-1",
        session_id="sess-1",
        token_expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        raw_claims={},
    )


def _sample_provider_row(
    provider_id: str = "prov-1",
    provider_type: str = "github",
    is_active: bool = True,
) -> GitProviderRow:
    """Build a sample GitProviderRow for mocked responses."""
    return GitProviderRow(
        id=provider_id,
        provider_type=provider_type,
        display_name="GitHub Cloud",
        base_url="https://api.github.com",
        client_id="gh-client-id",
        client_secret_encrypted="encrypted-secret",
        is_active=is_active,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_repo():
    """AsyncMock that mimics GitProviderRepository."""
    repo = AsyncMock()
    repo.list_providers = AsyncMock(return_value=[])
    repo.get_provider = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_git_provider():
    """AsyncMock that mimics a GitProvider adapter instance."""
    provider = AsyncMock()
    provider.aclose = AsyncMock()
    provider.list_accounts = AsyncMock(return_value=[])
    provider.list_account_repos = AsyncMock(return_value=[])
    provider.list_user_repos = AsyncMock(return_value=[])
    provider.list_branches = AsyncMock(return_value=[])
    provider.list_tree = AsyncMock(return_value=[])
    provider.get_file_content = AsyncMock(return_value=None)
    return provider


@pytest.fixture
async def client(mock_repo):
    """AsyncClient with an admin user session and mocked dependencies."""
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

        admin_session = _make_user_session()

        async def _set_user(request, call_next):
            request.state.user_session = admin_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture
async def reader_client(mock_repo):
    """AsyncClient with only knowledge:read permission."""
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

        reader_session = _make_user_session(permissions=["knowledge:read"])

        async def _set_user(request, call_next):
            request.state.user_session = reader_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# List providers
# ---------------------------------------------------------------------------


class TestListProviders:
    async def test_list_providers_empty(self, client, mock_repo):
        mock_repo.list_providers.return_value = []
        response = await client.get("/api/git/providers")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_providers_returns_active_only(self, client, mock_repo):
        active = _sample_provider_row("prov-1", is_active=True)
        inactive = _sample_provider_row("prov-2", is_active=False)
        mock_repo.list_providers.return_value = [active, inactive]

        response = await client.get("/api/git/providers")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "prov-1"
        assert data[0]["provider_type"] == "github"
        assert data[0]["display_name"] == "GitHub Cloud"
        assert data[0]["is_active"] is True

    async def test_list_providers_allowed_for_reader(self, reader_client, mock_repo):
        mock_repo.list_providers.return_value = [_sample_provider_row()]
        response = await reader_client.get("/api/git/providers")
        assert response.status_code == 200
        assert len(response.json()) == 1


# ---------------------------------------------------------------------------
# List accounts
# ---------------------------------------------------------------------------


class TestListAccounts:
    async def test_list_accounts(self, client, mock_repo, mock_git_provider):
        mock_repo.get_provider.return_value = _sample_provider_row()
        mock_git_provider.list_accounts.return_value = [
            GitAccount(login="firefly-org", avatar_url="https://img/1", description="Main org"),
            GitAccount(login="acme-corp", avatar_url="https://img/2", description=""),
        ]

        with patch(
            "flydesk.api.git_import.GitProviderFactory"
        ) as mock_factory:
            mock_factory.create.return_value = mock_git_provider
            response = await client.get(
                "/api/git/prov-1/accounts", params={"token": "ghp_test"}
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["login"] == "firefly-org"
        assert data[0]["avatar_url"] == "https://img/1"
        assert data[0]["description"] == "Main org"
        assert data[1]["login"] == "acme-corp"

    async def test_list_accounts_provider_not_found(self, client, mock_repo):
        mock_repo.get_provider.return_value = None
        response = await client.get(
            "/api/git/prov-999/accounts", params={"token": "ghp_test"}
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_list_accounts_inactive_provider(self, client, mock_repo):
        mock_repo.get_provider.return_value = _sample_provider_row(is_active=False)
        response = await client.get(
            "/api/git/prov-1/accounts", params={"token": "ghp_test"}
        )
        assert response.status_code == 404

    async def test_list_accounts_denied_for_reader(self, reader_client, mock_repo):
        response = await reader_client.get(
            "/api/git/prov-1/accounts", params={"token": "ghp_test"}
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# List repos
# ---------------------------------------------------------------------------


class TestListRepos:
    async def test_list_repos_for_account(self, client, mock_repo, mock_git_provider):
        mock_repo.get_provider.return_value = _sample_provider_row()
        mock_git_provider.list_account_repos.return_value = [
            GitRepo(
                full_name="firefly-org/api",
                name="api",
                owner="firefly-org",
                private=False,
                default_branch="main",
                description="API service",
                html_url="https://github.com/firefly-org/api",
            ),
        ]

        with patch(
            "flydesk.api.git_import.GitProviderFactory"
        ) as mock_factory:
            mock_factory.create.return_value = mock_git_provider
            response = await client.get(
                "/api/git/prov-1/repos",
                params={"token": "ghp_test", "account": "firefly-org"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["full_name"] == "firefly-org/api"
        assert data[0]["private"] is False

    async def test_list_repos_user_own(self, client, mock_repo, mock_git_provider):
        mock_repo.get_provider.return_value = _sample_provider_row()
        mock_git_provider.list_user_repos.return_value = [
            GitRepo(
                full_name="user/my-repo",
                name="my-repo",
                owner="user",
                private=True,
                default_branch="main",
            ),
        ]

        with patch(
            "flydesk.api.git_import.GitProviderFactory"
        ) as mock_factory:
            mock_factory.create.return_value = mock_git_provider
            response = await client.get(
                "/api/git/prov-1/repos", params={"token": "ghp_test"}
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["full_name"] == "user/my-repo"
        assert data[0]["private"] is True

    async def test_list_repos_with_search(self, client, mock_repo, mock_git_provider):
        mock_repo.get_provider.return_value = _sample_provider_row()
        mock_git_provider.list_account_repos.return_value = []

        with patch(
            "flydesk.api.git_import.GitProviderFactory"
        ) as mock_factory:
            mock_factory.create.return_value = mock_git_provider
            response = await client.get(
                "/api/git/prov-1/repos",
                params={"token": "ghp_test", "account": "org", "search": "api"},
            )

        assert response.status_code == 200
        mock_git_provider.list_account_repos.assert_awaited_once_with("org", search="api")

    async def test_list_repos_provider_not_found(self, client, mock_repo):
        mock_repo.get_provider.return_value = None
        response = await client.get(
            "/api/git/prov-999/repos", params={"token": "ghp_test"}
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# List branches
# ---------------------------------------------------------------------------


class TestListBranches:
    async def test_list_branches(self, client, mock_repo, mock_git_provider):
        mock_repo.get_provider.return_value = _sample_provider_row()
        mock_git_provider.list_branches.return_value = [
            GitBranch(name="main", sha="abc123"),
            GitBranch(name="develop", sha="def456"),
        ]

        with patch(
            "flydesk.api.git_import.GitProviderFactory"
        ) as mock_factory:
            mock_factory.create.return_value = mock_git_provider
            response = await client.get(
                "/api/git/prov-1/repos/octocat/hello/branches",
                params={"token": "ghp_test"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "main"
        assert data[0]["sha"] == "abc123"
        assert data[1]["name"] == "develop"

    async def test_list_branches_provider_not_found(self, client, mock_repo):
        mock_repo.get_provider.return_value = None
        response = await client.get(
            "/api/git/prov-999/repos/octocat/hello/branches",
            params={"token": "ghp_test"},
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# List tree
# ---------------------------------------------------------------------------


class TestListTree:
    async def test_list_tree(self, client, mock_repo, mock_git_provider):
        mock_repo.get_provider.return_value = _sample_provider_row()
        mock_git_provider.list_tree.return_value = [
            GitTreeEntry(path="README.md", sha="a1", size=100, type="blob"),
            GitTreeEntry(path="src/main.py", sha="a2", size=500, type="blob"),
        ]

        with patch(
            "flydesk.api.git_import.GitProviderFactory"
        ) as mock_factory:
            mock_factory.create.return_value = mock_git_provider
            response = await client.get(
                "/api/git/prov-1/repos/octocat/hello/tree/main",
                params={"token": "ghp_test"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["path"] == "README.md"
        assert data[0]["size"] == 100
        assert data[1]["path"] == "src/main.py"

    async def test_list_tree_branch_with_slash(self, client, mock_repo, mock_git_provider):
        """Branches like 'feature/add-login' contain slashes."""
        mock_repo.get_provider.return_value = _sample_provider_row()
        mock_git_provider.list_tree.return_value = [
            GitTreeEntry(path="file.txt", sha="a1", size=10),
        ]

        with patch(
            "flydesk.api.git_import.GitProviderFactory"
        ) as mock_factory:
            mock_factory.create.return_value = mock_git_provider
            response = await client.get(
                "/api/git/prov-1/repos/octocat/hello/tree/feature/add-login",
                params={"token": "ghp_test"},
            )

        assert response.status_code == 200
        mock_git_provider.list_tree.assert_awaited_once_with(
            "octocat", "hello", "feature/add-login"
        )


# ---------------------------------------------------------------------------
# Preview files
# ---------------------------------------------------------------------------


class TestPreviewFiles:
    async def test_preview_files(self, client, mock_repo, mock_git_provider):
        mock_repo.get_provider.return_value = _sample_provider_row()
        mock_git_provider.get_file_content.return_value = GitFileContent(
            path="README.md",
            sha="a1",
            content="# Hello World",
            encoding="utf-8",
            size=13,
        )

        with patch(
            "flydesk.api.git_import.GitProviderFactory"
        ) as mock_factory:
            mock_factory.create.return_value = mock_git_provider
            response = await client.post(
                "/api/git/prov-1/repos/octocat/hello/preview",
                json={"branch": "main", "paths": ["README.md"]},
                params={"token": "ghp_test"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["path"] == "README.md"
        assert data[0]["content"] == "# Hello World"
        assert data[0]["size"] == 13

    async def test_preview_files_partial_failure(self, client, mock_repo, mock_git_provider):
        """When one file fails to fetch, it returns an error entry for that file."""
        mock_repo.get_provider.return_value = _sample_provider_row()

        async def _get_file(owner, repo, path, ref=None):
            if path == "good.md":
                return GitFileContent(path="good.md", sha="a1", content="ok", size=2)
            raise RuntimeError("File not found")

        mock_git_provider.get_file_content = _get_file

        with patch(
            "flydesk.api.git_import.GitProviderFactory"
        ) as mock_factory:
            mock_factory.create.return_value = mock_git_provider
            response = await client.post(
                "/api/git/prov-1/repos/octocat/hello/preview",
                json={"branch": "main", "paths": ["good.md", "bad.md"]},
                params={"token": "ghp_test"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["path"] == "good.md"
        assert data[0]["content"] == "ok"
        assert data[1]["path"] == "bad.md"
        assert "error" in data[1]


# ---------------------------------------------------------------------------
# Import repos
# ---------------------------------------------------------------------------


class TestImportRepos:
    async def test_import_returns_accepted(self, client, mock_repo, mock_git_provider):
        mock_repo.get_provider.return_value = _sample_provider_row()

        with patch(
            "flydesk.api.git_import.GitProviderFactory"
        ) as mock_factory:
            mock_factory.create.return_value = mock_git_provider
            response = await client.post(
                "/api/git/prov-1/import",
                json={
                    "items": [
                        {
                            "owner": "octocat",
                            "repo": "hello",
                            "branch": "main",
                            "paths": ["README.md", "docs/guide.yaml"],
                            "tags": ["onboarding"],
                        },
                        {
                            "owner": "octocat",
                            "repo": "world",
                            "branch": "develop",
                            "paths": ["api.json"],
                        },
                    ]
                },
                params={"token": "ghp_test"},
            )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert len(data["items"]) == 3
        assert data["items"][0]["path"] == "README.md"
        assert data["items"][0]["repo"] == "octocat/hello"
        assert data["items"][0]["status"] == "queued"
        assert data["items"][2]["path"] == "api.json"
        assert data["items"][2]["repo"] == "octocat/world"

    async def test_import_provider_not_found(self, client, mock_repo):
        mock_repo.get_provider.return_value = None
        response = await client.post(
            "/api/git/prov-999/import",
            json={"items": []},
            params={"token": "ghp_test"},
        )
        assert response.status_code == 404

    async def test_import_denied_for_reader(self, reader_client, mock_repo):
        response = await reader_client.post(
            "/api/git/prov-1/import",
            json={"items": []},
            params={"token": "ghp_test"},
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Provider not found / inactive
# ---------------------------------------------------------------------------


class TestProviderNotFound:
    async def test_accounts_404_when_provider_missing(self, client, mock_repo):
        mock_repo.get_provider.return_value = None
        response = await client.get(
            "/api/git/nonexistent/accounts", params={"token": "tok"}
        )
        assert response.status_code == 404

    async def test_repos_404_when_provider_inactive(self, client, mock_repo):
        mock_repo.get_provider.return_value = _sample_provider_row(is_active=False)
        response = await client.get(
            "/api/git/prov-1/repos", params={"token": "tok"}
        )
        assert response.status_code == 404

    async def test_branches_404_when_provider_missing(self, client, mock_repo):
        mock_repo.get_provider.return_value = None
        response = await client.get(
            "/api/git/nonexistent/repos/o/r/branches", params={"token": "tok"}
        )
        assert response.status_code == 404

    async def test_tree_404_when_provider_missing(self, client, mock_repo):
        mock_repo.get_provider.return_value = None
        response = await client.get(
            "/api/git/nonexistent/repos/o/r/tree/main", params={"token": "tok"}
        )
        assert response.status_code == 404

    async def test_preview_404_when_provider_missing(self, client, mock_repo):
        mock_repo.get_provider.return_value = None
        response = await client.post(
            "/api/git/nonexistent/repos/o/r/preview",
            json={"branch": "main", "paths": ["x"]},
            params={"token": "tok"},
        )
        assert response.status_code == 404
