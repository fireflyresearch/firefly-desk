# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the GitHub REST API client."""

from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from flydesk.knowledge.github import (
    GITHUB_API_BASE,
    GitHubClient,
    exchange_oauth_code,
)


# ---------------------------------------------------------------------------
# Header / auth tests
# ---------------------------------------------------------------------------


class TestGitHubClientHeaders:
    def test_headers_with_token(self):
        client = GitHubClient(token="ghp_test123")
        assert client._client.headers["Authorization"] == "Bearer ghp_test123"
        assert "application/vnd.github+json" in client._client.headers["Accept"]

    def test_headers_without_token(self):
        client = GitHubClient(token=None)
        assert "Authorization" not in client._client.headers
        assert "application/vnd.github+json" in client._client.headers["Accept"]

    def test_is_authenticated_with_token(self):
        client = GitHubClient(token="ghp_test123")
        assert client.is_authenticated is True

    def test_is_authenticated_without_token(self):
        client = GitHubClient(token=None)
        assert client.is_authenticated is False


# ---------------------------------------------------------------------------
# list_user_repos
# ---------------------------------------------------------------------------


class TestListUserRepos:
    @pytest.mark.anyio
    async def test_list_user_repos_success(self):
        mock_response = httpx.Response(
            200,
            json=[
                {
                    "full_name": "octocat/Hello-World",
                    "name": "Hello-World",
                    "owner": {"login": "octocat"},
                    "private": False,
                    "default_branch": "main",
                    "description": "My first repo",
                    "html_url": "https://github.com/octocat/Hello-World",
                }
            ],
            request=httpx.Request("GET", f"{GITHUB_API_BASE}/user/repos"),
        )
        client = GitHubClient(token="ghp_test")
        client._client = AsyncMock(spec=httpx.AsyncClient)
        client._client.get = AsyncMock(return_value=mock_response)

        repos = await client.list_user_repos()
        assert len(repos) == 1
        assert repos[0].full_name == "octocat/Hello-World"
        assert repos[0].owner == "octocat"
        assert repos[0].private is False

    @pytest.mark.anyio
    async def test_list_user_repos_requires_token(self):
        client = GitHubClient(token=None)
        with pytest.raises(ValueError, match="token is required"):
            await client.list_user_repos()


# ---------------------------------------------------------------------------
# list_tree (filters importable files)
# ---------------------------------------------------------------------------


class TestListTree:
    @pytest.mark.anyio
    async def test_list_tree_filters_importable_files(self):
        mock_response = httpx.Response(
            200,
            json={
                "sha": "abc123",
                "tree": [
                    {"path": "README.md", "sha": "a1", "size": 100, "type": "blob"},
                    {"path": "src/main.py", "sha": "a2", "size": 200, "type": "blob"},
                    {"path": "docs/guide.yaml", "sha": "a3", "size": 50, "type": "blob"},
                    {"path": "config.json", "sha": "a4", "size": 30, "type": "blob"},
                    {"path": "notes.yml", "sha": "a5", "size": 20, "type": "blob"},
                    {"path": "images", "sha": "a6", "size": 0, "type": "tree"},
                    {"path": "logo.png", "sha": "a7", "size": 500, "type": "blob"},
                ],
            },
            request=httpx.Request("GET", f"{GITHUB_API_BASE}/repos/o/r/git/trees/main"),
        )
        client = GitHubClient(token="ghp_test")
        client._client = AsyncMock(spec=httpx.AsyncClient)
        client._client.get = AsyncMock(return_value=mock_response)

        entries = await client.list_tree("o", "r", "main")
        paths = [e.path for e in entries]
        assert "README.md" in paths
        assert "docs/guide.yaml" in paths
        assert "config.json" in paths
        assert "notes.yml" in paths
        # Non-importable files should be excluded
        assert "src/main.py" not in paths
        assert "logo.png" not in paths
        # Directories should be excluded
        assert "images" not in paths


# ---------------------------------------------------------------------------
# get_file_content (base64 decode)
# ---------------------------------------------------------------------------


class TestGetFileContent:
    @pytest.mark.anyio
    async def test_get_file_content_decodes_base64(self):
        original = "# Hello World\n\nThis is a test."
        encoded = base64.b64encode(original.encode()).decode()
        mock_response = httpx.Response(
            200,
            json={
                "path": "README.md",
                "sha": "abc123",
                "content": encoded,
                "size": len(original),
            },
            request=httpx.Request("GET", f"{GITHUB_API_BASE}/repos/o/r/contents/README.md"),
        )
        client = GitHubClient(token="ghp_test")
        client._client = AsyncMock(spec=httpx.AsyncClient)
        client._client.get = AsyncMock(return_value=mock_response)

        fc = await client.get_file_content("o", "r", "README.md", ref="main")
        assert fc.content == original
        assert fc.path == "README.md"
        assert fc.sha == "abc123"


# ---------------------------------------------------------------------------
# exchange_oauth_code
# ---------------------------------------------------------------------------


class TestExchangeOAuthCode:
    @pytest.mark.anyio
    async def test_exchange_oauth_code_success(self):
        mock_response = httpx.Response(
            200,
            json={"access_token": "gho_abc123", "token_type": "bearer", "scope": "repo"},
            request=httpx.Request("POST", "https://github.com/login/oauth/access_token"),
        )
        with patch("flydesk.knowledge.github.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            token = await exchange_oauth_code("client-id", "client-secret", "code-123")
            assert token == "gho_abc123"

    @pytest.mark.anyio
    async def test_exchange_oauth_code_error(self):
        mock_response = httpx.Response(
            200,
            json={"error": "bad_verification_code", "error_description": "The code is invalid"},
            request=httpx.Request("POST", "https://github.com/login/oauth/access_token"),
        )
        with patch("flydesk.knowledge.github.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            with pytest.raises(ValueError, match="code is invalid"):
                await exchange_oauth_code("client-id", "client-secret", "bad-code")
