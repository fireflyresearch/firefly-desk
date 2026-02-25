# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests verifying Git import endpoints are wired to the IndexingQueueProducer."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from flydesk.auth.models import UserSession
from flydesk.knowledge.git_provider import GitFileContent
from flydesk.knowledge.queue import IndexingTask
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

ENV = {
    "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
    "FLYDESK_OIDC_CLIENT_ID": "test",
    "FLYDESK_OIDC_CLIENT_SECRET": "test",
    "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
}


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
    provider.get_file_content = AsyncMock(
        return_value=GitFileContent(
            path="README.md",
            sha="abc123",
            content="# Hello",
            encoding="utf-8",
            size=7,
        )
    )
    return provider


@pytest.fixture
def mock_producer():
    """AsyncMock that mimics IndexingQueueProducer."""
    producer = AsyncMock()
    producer.enqueue = AsyncMock()
    return producer


@pytest.fixture
async def unified_client(mock_repo, mock_producer):
    """AsyncClient for the unified /api/git endpoints with mocked producer."""
    with patch.dict(os.environ, ENV):
        from flydesk.api.git_providers import get_git_provider_repo
        from flydesk.api.knowledge import get_indexing_producer
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_git_provider_repo] = lambda: mock_repo
        app.dependency_overrides[get_indexing_producer] = lambda: mock_producer

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
async def github_client(mock_producer):
    """AsyncClient for the /api/github endpoints with mocked producer."""
    with patch.dict(os.environ, ENV):
        from flydesk.api.knowledge import get_indexing_producer
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_indexing_producer] = lambda: mock_producer

        admin_session = _make_user_session()

        async def _set_user(request, call_next):
            request.state.user_session = admin_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# Unified import endpoint (/api/git/{provider_id}/import)
# ---------------------------------------------------------------------------


class TestUnifiedImportIndexing:
    """Tests for the provider-agnostic import endpoint wired to the indexer."""

    async def test_import_enqueues_tasks(
        self, unified_client, mock_repo, mock_git_provider, mock_producer
    ):
        """Each file in the import cart should be enqueued via the producer."""
        mock_repo.get_provider.return_value = _sample_provider_row()

        mock_git_provider.get_file_content = AsyncMock(
            side_effect=[
                GitFileContent(path="README.md", sha="sha1", content="# Readme", size=8),
                GitFileContent(path="docs/guide.md", sha="sha2", content="Guide text", size=10),
            ]
        )

        with patch("flydesk.api.git_import.GitProviderFactory") as mock_factory:
            mock_factory.create.return_value = mock_git_provider
            response = await unified_client.post(
                "/api/git/prov-1/import",
                json={
                    "items": [
                        {
                            "owner": "octocat",
                            "repo": "hello",
                            "branch": "main",
                            "paths": ["README.md", "docs/guide.md"],
                            "tags": ["onboarding"],
                        }
                    ]
                },
                params={"token": "ghp_test"},
            )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert len(data["items"]) == 2

        # Verify both items report queued with document_id
        assert data["items"][0]["status"] == "queued"
        assert "document_id" in data["items"][0]
        assert data["items"][0]["path"] == "README.md"

        assert data["items"][1]["status"] == "queued"
        assert "document_id" in data["items"][1]
        assert data["items"][1]["path"] == "docs/guide.md"

        # Verify enqueue was called twice
        assert mock_producer.enqueue.await_count == 2

    async def test_indexing_task_fields(
        self, unified_client, mock_repo, mock_git_provider, mock_producer
    ):
        """Verify the IndexingTask passed to enqueue has correct fields."""
        mock_repo.get_provider.return_value = _sample_provider_row()
        mock_git_provider.get_file_content = AsyncMock(
            return_value=GitFileContent(
                path="src/main.py", sha="abc999", content="print('hello')", size=15
            )
        )

        with patch("flydesk.api.git_import.GitProviderFactory") as mock_factory:
            mock_factory.create.return_value = mock_git_provider
            await unified_client.post(
                "/api/git/prov-1/import",
                json={
                    "items": [
                        {
                            "owner": "acme",
                            "repo": "lib",
                            "branch": "develop",
                            "paths": ["src/main.py"],
                            "tags": ["python"],
                        }
                    ]
                },
                params={"token": "ghp_test"},
            )

        # Inspect the task passed to enqueue
        task: IndexingTask = mock_producer.enqueue.call_args_list[0][0][0]
        assert task.content == "print('hello')"
        assert task.title == "main"  # filename without extension
        assert task.source == "git://acme/lib/src/main.py@develop"
        assert "python" in task.tags
        assert "git-import" in task.tags
        assert "repo:acme/lib" in task.tags
        assert task.metadata["provider"] == "prov-1"
        assert task.metadata["repo"] == "acme/lib"
        assert task.metadata["branch"] == "develop"
        assert task.metadata["path"] == "src/main.py"
        assert task.metadata["sha"] == "abc999"

    async def test_import_per_file_error_handling(
        self, unified_client, mock_repo, mock_git_provider, mock_producer
    ):
        """When a file fetch fails, it should report the error for that file only."""
        mock_repo.get_provider.return_value = _sample_provider_row()

        async def _get_file(owner, repo, path, ref=None):
            if path == "good.md":
                return GitFileContent(path="good.md", sha="sha1", content="ok", size=2)
            raise RuntimeError("File not found on remote")

        mock_git_provider.get_file_content = _get_file

        with patch("flydesk.api.git_import.GitProviderFactory") as mock_factory:
            mock_factory.create.return_value = mock_git_provider
            response = await unified_client.post(
                "/api/git/prov-1/import",
                json={
                    "items": [
                        {
                            "owner": "octocat",
                            "repo": "hello",
                            "branch": "main",
                            "paths": ["good.md", "bad.md"],
                        }
                    ]
                },
                params={"token": "ghp_test"},
            )

        assert response.status_code == 202
        data = response.json()
        assert len(data["items"]) == 2

        # good.md should be queued
        assert data["items"][0]["path"] == "good.md"
        assert data["items"][0]["status"] == "queued"
        assert "document_id" in data["items"][0]

        # bad.md should report the error
        assert data["items"][1]["path"] == "bad.md"
        assert data["items"][1]["status"] == "failed"
        assert "File not found on remote" in data["items"][1]["error"]

        # Only 1 task should have been enqueued
        assert mock_producer.enqueue.await_count == 1

    async def test_import_multi_repo_cart(
        self, unified_client, mock_repo, mock_git_provider, mock_producer
    ):
        """Multiple repos in a single cart should all be processed."""
        mock_repo.get_provider.return_value = _sample_provider_row()
        mock_git_provider.get_file_content = AsyncMock(
            return_value=GitFileContent(path="f.md", sha="s1", content="c", size=1)
        )

        with patch("flydesk.api.git_import.GitProviderFactory") as mock_factory:
            mock_factory.create.return_value = mock_git_provider
            response = await unified_client.post(
                "/api/git/prov-1/import",
                json={
                    "items": [
                        {
                            "owner": "org1",
                            "repo": "repo1",
                            "branch": "main",
                            "paths": ["a.md"],
                        },
                        {
                            "owner": "org2",
                            "repo": "repo2",
                            "branch": "dev",
                            "paths": ["b.md", "c.md"],
                        },
                    ]
                },
                params={"token": "ghp_test"},
            )

        assert response.status_code == 202
        data = response.json()
        assert len(data["items"]) == 3
        assert mock_producer.enqueue.await_count == 3


# ---------------------------------------------------------------------------
# GitHub import endpoint (/api/github/repos/{owner}/{repo}/import)
# ---------------------------------------------------------------------------


class TestGitHubImportIndexing:
    """Tests for the legacy GitHub import endpoint wired to the indexer."""

    async def test_github_import_calls_producer(
        self, github_client, mock_producer
    ):
        """The GitHub import endpoint should enqueue an IndexingTask per file."""
        mock_github_client = AsyncMock()
        mock_github_client.aclose = AsyncMock()
        mock_github_client.get_file_content = AsyncMock(
            side_effect=[
                GitFileContent(path="README.md", sha="sha1", content="# Hello", size=7),
                GitFileContent(path="api.yaml", sha="sha2", content="openapi: 3", size=11),
            ]
        )

        with patch("flydesk.api.github._make_client", return_value=mock_github_client):
            response = await github_client.post(
                "/api/github/repos/octocat/hello/import",
                json={
                    "paths": ["README.md", "api.yaml"],
                    "branch": "main",
                    "tags": ["docs"],
                },
                params={"token": "ghp_test"},
            )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["files"] == 2

        # Verify enqueue was called for each file
        assert mock_producer.enqueue.await_count == 2

    async def test_github_import_task_fields(
        self, github_client, mock_producer
    ):
        """Verify IndexingTask fields from the GitHub import endpoint."""
        mock_github_client = AsyncMock()
        mock_github_client.aclose = AsyncMock()
        mock_github_client.get_file_content = AsyncMock(
            return_value=GitFileContent(
                path="docs/setup.md", sha="def456", content="Setup instructions", size=19
            )
        )

        with patch("flydesk.api.github._make_client", return_value=mock_github_client):
            await github_client.post(
                "/api/github/repos/firefly/desk/import",
                json={
                    "paths": ["docs/setup.md"],
                    "branch": "release",
                    "tags": ["setup"],
                },
                params={"token": "ghp_test"},
            )

        task: IndexingTask = mock_producer.enqueue.call_args_list[0][0][0]
        assert task.content == "Setup instructions"
        assert task.title == "setup"
        assert task.source == "git://firefly/desk/docs/setup.md@release"
        assert "setup" in task.tags
        assert "git-import" in task.tags
        assert "repo:firefly/desk" in task.tags
        assert task.metadata["provider"] == "github"
        assert task.metadata["repo"] == "firefly/desk"
        assert task.metadata["branch"] == "release"
        assert task.metadata["path"] == "docs/setup.md"
        assert task.metadata["sha"] == "def456"

    async def test_github_import_no_longer_placeholder(
        self, github_client, mock_producer
    ):
        """The endpoint should actually call the Git client, not just return a count."""
        mock_github_client = AsyncMock()
        mock_github_client.aclose = AsyncMock()
        mock_github_client.get_file_content = AsyncMock(
            return_value=GitFileContent(path="f.md", sha="s", content="c", size=1)
        )

        with patch("flydesk.api.github._make_client", return_value=mock_github_client):
            response = await github_client.post(
                "/api/github/repos/org/repo/import",
                json={"paths": ["f.md"], "branch": "main"},
                params={"token": "ghp_test"},
            )

        assert response.status_code == 202
        # Verify that get_file_content was actually called
        mock_github_client.get_file_content.assert_awaited_once_with(
            "org", "repo", "f.md", ref="main"
        )
        # And enqueue was called
        mock_producer.enqueue.assert_awaited_once()
