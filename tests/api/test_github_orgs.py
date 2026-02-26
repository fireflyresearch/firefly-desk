# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for GitHub organization API routes.

These tests create a minimal FastAPI app directly from the router module
to avoid issues with the editable install pointing at the main tree
when running from a worktree.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _build_app() -> FastAPI:
    """Build a minimal FastAPI app containing only the GitHub router."""
    import flydesk.api.github as gh_api

    app = FastAPI()
    app.include_router(gh_api.router)
    return app


@pytest.fixture
async def client():
    """AsyncClient wired to a minimal app containing only the GitHub router."""
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# list_organizations
# ---------------------------------------------------------------------------


class TestListOrganizations:
    @pytest.mark.anyio
    async def test_list_organizations_returns_orgs(self, client):
        mock_orgs = [
            {"login": "firefly-org", "avatar_url": "https://avatars.example.com/1", "description": "Firefly Org"},
            {"login": "acme-corp", "avatar_url": "https://avatars.example.com/2", "description": ""},
        ]

        with patch("flydesk.api.github._make_client") as mock_make:
            mock_gh = AsyncMock()
            mock_gh.list_user_organizations = AsyncMock(return_value=mock_orgs)
            mock_gh.aclose = AsyncMock()
            mock_make.return_value = mock_gh

            response = await client.get(
                "/api/github/orgs",
                params={"token": "ghp_test"},
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["login"] == "firefly-org"
            assert data[0]["avatar_url"] == "https://avatars.example.com/1"
            assert data[0]["description"] == "Firefly Org"
            assert data[1]["login"] == "acme-corp"

    @pytest.mark.anyio
    async def test_list_organizations_requires_token(self, client):
        response = await client.get("/api/github/orgs")
        assert response.status_code == 422  # Missing required query param

    @pytest.mark.anyio
    async def test_list_organizations_empty(self, client):
        with patch("flydesk.api.github._make_client") as mock_make:
            mock_gh = AsyncMock()
            mock_gh.list_user_organizations = AsyncMock(return_value=[])
            mock_gh.aclose = AsyncMock()
            mock_make.return_value = mock_gh

            response = await client.get(
                "/api/github/orgs",
                params={"token": "ghp_test"},
            )
            assert response.status_code == 200
            assert response.json() == []


# ---------------------------------------------------------------------------
# list_org_repos
# ---------------------------------------------------------------------------


class TestListOrgRepos:
    @pytest.mark.anyio
    async def test_list_org_repos_returns_repos(self, client):
        from flydesk.knowledge.github import GitHubRepo

        mock_repos = [
            GitHubRepo(
                full_name="firefly-org/api-gateway",
                name="api-gateway",
                owner="firefly-org",
                private=False,
                default_branch="main",
                description="API Gateway service",
                html_url="https://github.com/firefly-org/api-gateway",
            ),
            GitHubRepo(
                full_name="firefly-org/web-app",
                name="web-app",
                owner="firefly-org",
                private=True,
                default_branch="develop",
                description="Web application",
                html_url="https://github.com/firefly-org/web-app",
            ),
        ]

        with patch("flydesk.api.github._make_client") as mock_make:
            mock_gh = AsyncMock()
            mock_gh.list_org_repos = AsyncMock(return_value=mock_repos)
            mock_gh.aclose = AsyncMock()
            mock_make.return_value = mock_gh

            response = await client.get(
                "/api/github/orgs/firefly-org/repos",
                params={"token": "ghp_test"},
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["full_name"] == "firefly-org/api-gateway"
            assert data[0]["private"] is False
            assert data[1]["full_name"] == "firefly-org/web-app"
            assert data[1]["private"] is True

    @pytest.mark.anyio
    async def test_list_org_repos_with_search_filter(self, client):
        from flydesk.knowledge.github import GitHubRepo

        mock_repos = [
            GitHubRepo(
                full_name="firefly-org/api-gateway",
                name="api-gateway",
                owner="firefly-org",
                private=False,
                default_branch="main",
                description="API Gateway",
                html_url="",
            ),
            GitHubRepo(
                full_name="firefly-org/web-app",
                name="web-app",
                owner="firefly-org",
                private=False,
                default_branch="main",
                description="Web app",
                html_url="",
            ),
        ]

        with patch("flydesk.api.github._make_client") as mock_make:
            mock_gh = AsyncMock()
            mock_gh.list_org_repos = AsyncMock(return_value=mock_repos)
            mock_gh.aclose = AsyncMock()
            mock_make.return_value = mock_gh

            response = await client.get(
                "/api/github/orgs/firefly-org/repos",
                params={"token": "ghp_test", "search": "api"},
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["full_name"] == "firefly-org/api-gateway"

    @pytest.mark.anyio
    async def test_list_org_repos_requires_token(self, client):
        response = await client.get("/api/github/orgs/firefly-org/repos")
        assert response.status_code == 422  # Missing required query param

    @pytest.mark.anyio
    async def test_list_org_repos_search_case_insensitive(self, client):
        from flydesk.knowledge.github import GitHubRepo

        mock_repos = [
            GitHubRepo(
                full_name="firefly-org/API-Gateway",
                name="API-Gateway",
                owner="firefly-org",
                private=False,
                default_branch="main",
                description="",
                html_url="",
            ),
        ]

        with patch("flydesk.api.github._make_client") as mock_make:
            mock_gh = AsyncMock()
            mock_gh.list_org_repos = AsyncMock(return_value=mock_repos)
            mock_gh.aclose = AsyncMock()
            mock_make.return_value = mock_gh

            response = await client.get(
                "/api/github/orgs/firefly-org/repos",
                params={"token": "ghp_test", "search": "api-gateway"},
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["full_name"] == "firefly-org/API-Gateway"
