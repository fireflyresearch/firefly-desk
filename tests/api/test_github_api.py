# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the GitHub API routes."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from flydesk.knowledge.git_provider import GitFileContent
from flydesk.knowledge.github import GitHubBranch, GitHubTreeEntry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_producer():
    """AsyncMock that mimics IndexingQueueProducer."""
    producer = AsyncMock()
    producer.enqueue = AsyncMock()
    return producer


@pytest.fixture
async def client(mock_producer):
    """AsyncClient wired to a minimal app with the GitHub router."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
        "FLYDESK_GITHUB_CLIENT_ID": "gh-client-id",
        "FLYDESK_GITHUB_CLIENT_SECRET": "gh-client-secret",
    }
    with patch.dict(os.environ, env):
        from flydesk.api.knowledge import get_indexing_producer
        from flydesk.config import get_config
        from flydesk.server import create_app

        get_config.cache_clear()
        app = create_app()
        app.dependency_overrides[get_indexing_producer] = lambda: mock_producer

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# OAuth URL
# ---------------------------------------------------------------------------


class TestOAuthURL:
    @pytest.mark.anyio
    async def test_oauth_url_returns_github_auth_url(self, client):
        response = await client.get("/api/github/auth/url")
        assert response.status_code == 200
        data = response.json()
        assert "url" in data
        assert "github.com/login/oauth/authorize" in data["url"]
        assert "client_id=gh-client-id" in data["url"]


# ---------------------------------------------------------------------------
# Repos
# ---------------------------------------------------------------------------


class TestRepos:
    @pytest.mark.anyio
    async def test_repos_requires_token_or_search(self, client):
        response = await client.get("/api/github/repos")
        assert response.status_code == 400
        assert "token" in response.json()["detail"].lower() or "search" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Tree
# ---------------------------------------------------------------------------


class TestTree:
    @pytest.mark.anyio
    async def test_list_tree_returns_classified_files(self, client):
        mock_entries = [
            GitHubTreeEntry(path="README.md", sha="a1", size=100),
            GitHubTreeEntry(path="config.json", sha="a2", size=50),
            GitHubTreeEntry(path="openapi.yaml", sha="a3", size=200),
            GitHubTreeEntry(path="data.yml", sha="a4", size=30),
        ]

        with patch(
            "flydesk.api.github._make_client"
        ) as mock_make:
            mock_gh = AsyncMock()
            mock_gh.list_tree = AsyncMock(return_value=mock_entries)
            mock_gh.aclose = AsyncMock()
            mock_make.return_value = mock_gh

            response = await client.get(
                "/api/github/repos/octocat/Hello-World/tree/main",
                params={"token": "ghp_test"},
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 4

            # Check classification
            by_path = {e["path"]: e for e in data}
            assert by_path["README.md"]["file_type"] == "markdown"
            assert by_path["config.json"]["file_type"] == "data"
            assert by_path["openapi.yaml"]["file_type"] == "openapi"
            assert by_path["data.yml"]["file_type"] == "data"


# ---------------------------------------------------------------------------
# Import placeholder
# ---------------------------------------------------------------------------


class TestImport:
    @pytest.mark.anyio
    async def test_import_returns_accepted(self, client):
        mock_gh = AsyncMock()
        mock_gh.get_file_content = AsyncMock(
            return_value=GitFileContent(
                path="f.md", sha="sha1", content="content", size=7
            )
        )
        mock_gh.aclose = AsyncMock()

        with patch("flydesk.api.github._make_client", return_value=mock_gh):
            response = await client.post(
                "/api/github/repos/octocat/Hello-World/import",
                json={"paths": ["README.md", "docs/guide.yaml"], "branch": "main"},
            )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["files"] == 2
