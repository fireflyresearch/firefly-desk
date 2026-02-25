# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the Bitbucket Cloud REST API 2.0 adapter (BitbucketAdapter)."""

from __future__ import annotations

from unittest.mock import AsyncMock, call

import httpx
import pytest

from flydesk.knowledge.git_provider import (
    GitAccount,
    GitBranch,
    GitFileContent,
    GitProvider,
    GitProviderFactory,
    GitRepo,
    GitTreeEntry,
)
from flydesk.knowledge.bitbucket import BitbucketAdapter


BITBUCKET_API_BASE = "https://api.bitbucket.org/2.0"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_adapter(
    token: str = "bb-test-token",
    base_url: str | None = None,
) -> BitbucketAdapter:
    """Return a BitbucketAdapter with its internal httpx client mocked."""
    adapter = BitbucketAdapter(token=token, base_url=base_url)
    adapter._client = AsyncMock(spec=httpx.AsyncClient)
    return adapter


def _resp(
    status: int,
    json_data: dict | list | None = None,
    text: str = "",
    method: str = "GET",
    url: str = BITBUCKET_API_BASE,
) -> httpx.Response:
    """Build a fake httpx.Response."""
    if json_data is not None:
        return httpx.Response(
            status,
            json=json_data,
            request=httpx.Request(method, url),
        )
    return httpx.Response(
        status,
        text=text,
        request=httpx.Request(method, url),
    )


# ---------------------------------------------------------------------------
# Construction / headers
# ---------------------------------------------------------------------------


class TestBitbucketAdapterConstruction:
    def test_default_base_url(self):
        adapter = BitbucketAdapter(token="bb-test")
        assert str(adapter._client.base_url).rstrip("/") == BITBUCKET_API_BASE

    def test_custom_base_url(self):
        adapter = BitbucketAdapter(
            token="bb-test", base_url="https://bitbucket.corp.example.com/2.0"
        )
        expected = "https://bitbucket.corp.example.com/2.0"
        assert str(adapter._client.base_url).rstrip("/") == expected

    def test_trailing_slash_stripped(self):
        adapter = BitbucketAdapter(
            token="bb-test", base_url="https://api.bitbucket.org/2.0/"
        )
        expected = "https://api.bitbucket.org/2.0"
        assert str(adapter._client.base_url).rstrip("/") == expected

    def test_bearer_token_header_set(self):
        adapter = BitbucketAdapter(token="bb-abc")
        assert adapter._client.headers["Authorization"] == "Bearer bb-abc"

    def test_no_token_no_auth_header(self):
        adapter = BitbucketAdapter(token=None)
        assert "Authorization" not in adapter._client.headers

    def test_provider_type_is_bitbucket(self):
        adapter = BitbucketAdapter(token="bb-test")
        assert adapter.provider_type == "bitbucket"

    def test_accept_header_set(self):
        adapter = BitbucketAdapter(token="bb-test")
        assert adapter._client.headers["Accept"] == "application/json"


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    def test_bitbucket_adapter_is_git_provider(self):
        adapter = BitbucketAdapter(token="bb-test")
        assert isinstance(adapter, GitProvider)


# ---------------------------------------------------------------------------
# Factory registration
# ---------------------------------------------------------------------------


class TestFactoryRegistration:
    def test_factory_creates_bitbucket_adapter(self):
        # Ensure the import triggered registration
        provider = GitProviderFactory.create("bitbucket", token="bb-test")
        assert isinstance(provider, BitbucketAdapter)
        assert isinstance(provider, GitProvider)
        assert provider.provider_type == "bitbucket"

    def test_factory_passes_base_url(self):
        provider = GitProviderFactory.create(
            "bitbucket",
            token="bb-test",
            base_url="https://bitbucket.corp.example.com/2.0",
        )
        assert isinstance(provider, BitbucketAdapter)
        expected = "https://bitbucket.corp.example.com/2.0"
        assert str(provider._client.base_url).rstrip("/") == expected


# ---------------------------------------------------------------------------
# validate_token
# ---------------------------------------------------------------------------


class TestValidateToken:
    @pytest.mark.anyio
    async def test_validate_token_success(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            return_value=_resp(200, {"username": "testuser", "uuid": "{abc-123}"})
        )
        result = await adapter.validate_token()
        assert result is True
        adapter._client.get.assert_awaited_once_with("/user")

    @pytest.mark.anyio
    async def test_validate_token_unauthorized(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            return_value=_resp(401, {"type": "error", "error": {"message": "Unauthorized"}})
        )
        result = await adapter.validate_token()
        assert result is False


# ---------------------------------------------------------------------------
# list_accounts (Bitbucket workspaces)
# ---------------------------------------------------------------------------


class TestListAccounts:
    @pytest.mark.anyio
    async def test_list_accounts_returns_workspaces(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            return_value=_resp(
                200,
                {
                    "values": [
                        {
                            "slug": "firefly-ws",
                            "name": "Firefly Workspace",
                            "uuid": "{ws-1}",
                            "links": {
                                "avatar": {
                                    "href": "https://bitbucket.org/img/ws1.png"
                                }
                            },
                        },
                        {
                            "slug": "acme-ws",
                            "name": "Acme Corp",
                            "uuid": "{ws-2}",
                            "links": {},
                        },
                    ],
                },
            )
        )
        accounts = await adapter.list_accounts()
        assert len(accounts) == 2
        assert all(isinstance(a, GitAccount) for a in accounts)
        assert accounts[0].login == "firefly-ws"
        assert accounts[0].avatar_url == "https://bitbucket.org/img/ws1.png"
        assert accounts[0].description == "Firefly Workspace"
        # Missing avatar link should default to empty string
        assert accounts[1].avatar_url == ""
        assert accounts[1].description == "Acme Corp"

    @pytest.mark.anyio
    async def test_list_accounts_passes_pagelen(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            return_value=_resp(200, {"values": []})
        )
        await adapter.list_accounts()
        adapter._client.get.assert_awaited_once_with(
            "/workspaces",
            params={"pagelen": 100},
        )

    @pytest.mark.anyio
    async def test_list_accounts_null_name(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            return_value=_resp(
                200,
                {
                    "values": [
                        {
                            "slug": "ws-no-name",
                            "name": None,
                            "links": {"avatar": {"href": ""}},
                        },
                    ],
                },
            )
        )
        accounts = await adapter.list_accounts()
        assert accounts[0].description == ""


# ---------------------------------------------------------------------------
# list_account_repos (workspace repos)
# ---------------------------------------------------------------------------


class TestListAccountRepos:
    @pytest.mark.anyio
    async def test_list_account_repos_success(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            return_value=_resp(
                200,
                {
                    "values": [
                        {
                            "full_name": "firefly-ws/api-gateway",
                            "name": "api-gateway",
                            "is_private": False,
                            "mainbranch": {"name": "main"},
                            "description": "API Gateway service",
                            "links": {
                                "html": {
                                    "href": "https://bitbucket.org/firefly-ws/api-gateway"
                                }
                            },
                        },
                        {
                            "full_name": "firefly-ws/web-app",
                            "name": "web-app",
                            "is_private": True,
                            "mainbranch": {"name": "develop"},
                            "description": "Frontend",
                            "links": {
                                "html": {
                                    "href": "https://bitbucket.org/firefly-ws/web-app"
                                }
                            },
                        },
                    ],
                },
            )
        )
        repos = await adapter.list_account_repos("firefly-ws")
        assert len(repos) == 2
        assert all(isinstance(r, GitRepo) for r in repos)
        assert repos[0].full_name == "firefly-ws/api-gateway"
        assert repos[0].name == "api-gateway"
        assert repos[0].owner == "firefly-ws"
        assert repos[0].private is False
        assert repos[0].default_branch == "main"
        assert repos[0].html_url == "https://bitbucket.org/firefly-ws/api-gateway"
        assert repos[1].private is True
        assert repos[1].default_branch == "develop"

    @pytest.mark.anyio
    async def test_list_account_repos_with_search(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            return_value=_resp(200, {"values": []})
        )
        await adapter.list_account_repos("firefly-ws", search="api")
        adapter._client.get.assert_awaited_once()
        call_args = adapter._client.get.call_args
        assert call_args[1]["params"]["q"] == 'name~"api"'
        assert call_args[1]["params"]["pagelen"] == 100

    @pytest.mark.anyio
    async def test_list_account_repos_no_search_omits_q_param(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            return_value=_resp(200, {"values": []})
        )
        await adapter.list_account_repos("firefly-ws")
        call_args = adapter._client.get.call_args
        assert "q" not in call_args[1]["params"]


# ---------------------------------------------------------------------------
# list_user_repos
# ---------------------------------------------------------------------------


class TestListUserRepos:
    @pytest.mark.anyio
    async def test_list_user_repos_success(self):
        adapter = _mock_adapter()
        # First call: /user, second call: /repositories/{username}
        adapter._client.get = AsyncMock(
            side_effect=[
                _resp(200, {"username": "jdoe", "uuid": "{user-1}"}),
                _resp(
                    200,
                    {
                        "values": [
                            {
                                "full_name": "jdoe/my-project",
                                "name": "my-project",
                                "is_private": False,
                                "mainbranch": {"name": "main"},
                                "description": "My project",
                                "links": {
                                    "html": {
                                        "href": "https://bitbucket.org/jdoe/my-project"
                                    }
                                },
                            },
                        ],
                    },
                ),
            ]
        )
        repos = await adapter.list_user_repos()
        assert len(repos) == 1
        r = repos[0]
        assert isinstance(r, GitRepo)
        assert r.full_name == "jdoe/my-project"
        assert r.name == "my-project"
        assert r.owner == "jdoe"
        assert r.private is False
        assert r.html_url == "https://bitbucket.org/jdoe/my-project"

    @pytest.mark.anyio
    async def test_list_user_repos_with_search(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            side_effect=[
                _resp(200, {"username": "jdoe"}),
                _resp(200, {"values": []}),
            ]
        )
        await adapter.list_user_repos(search="tool")
        # Second call should include the search query
        second_call = adapter._client.get.call_args_list[1]
        assert second_call[1]["params"]["q"] == 'name~"tool"'
        assert second_call[1]["params"]["role"] == "member"

    @pytest.mark.anyio
    async def test_list_user_repos_no_search_omits_q_param(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            side_effect=[
                _resp(200, {"username": "jdoe"}),
                _resp(200, {"values": []}),
            ]
        )
        await adapter.list_user_repos()
        second_call = adapter._client.get.call_args_list[1]
        assert "q" not in second_call[1]["params"]


# ---------------------------------------------------------------------------
# list_branches
# ---------------------------------------------------------------------------


class TestListBranches:
    @pytest.mark.anyio
    async def test_list_branches_success(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            return_value=_resp(
                200,
                {
                    "values": [
                        {"name": "main", "target": {"hash": "abc123def456"}},
                        {"name": "develop", "target": {"hash": "789ghi012jkl"}},
                    ],
                },
            )
        )
        branches = await adapter.list_branches("firefly-ws", "api-gateway")
        assert len(branches) == 2
        assert all(isinstance(b, GitBranch) for b in branches)
        assert branches[0].name == "main"
        assert branches[0].sha == "abc123def456"
        assert branches[1].name == "develop"
        assert branches[1].sha == "789ghi012jkl"

    @pytest.mark.anyio
    async def test_list_branches_correct_url(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            return_value=_resp(200, {"values": []})
        )
        await adapter.list_branches("ws", "repo")
        call_args = adapter._client.get.call_args
        assert call_args[0][0] == "/repositories/ws/repo/refs/branches"
        assert call_args[1]["params"]["pagelen"] == 100


# ---------------------------------------------------------------------------
# list_tree (recursive directory traversal)
# ---------------------------------------------------------------------------


class TestListTree:
    @pytest.mark.anyio
    async def test_list_tree_filters_importable(self):
        adapter = _mock_adapter()
        # Root directory listing
        adapter._client.get = AsyncMock(
            return_value=_resp(
                200,
                {
                    "values": [
                        {
                            "type": "commit_file",
                            "path": "README.md",
                            "size": 100,
                            "commit": {"hash": "a1b2c3"},
                        },
                        {
                            "type": "commit_file",
                            "path": "src/main.py",
                            "size": 500,
                            "commit": {"hash": "d4e5f6"},
                        },
                        {
                            "type": "commit_file",
                            "path": "config.json",
                            "size": 50,
                            "commit": {"hash": "g7h8i9"},
                        },
                        {
                            "type": "commit_file",
                            "path": "data.yaml",
                            "size": 200,
                            "commit": {"hash": "j0k1l2"},
                        },
                        {
                            "type": "commit_file",
                            "path": "notes.yml",
                            "size": 150,
                            "commit": {"hash": "m3n4o5"},
                        },
                        {
                            "type": "commit_file",
                            "path": "logo.png",
                            "size": 10000,
                            "commit": {"hash": "p6q7r8"},
                        },
                    ],
                },
            )
        )
        entries = await adapter.list_tree("ws", "repo", "main")
        paths = [e.path for e in entries]
        # Importable files should be included
        assert "README.md" in paths
        assert "config.json" in paths
        assert "data.yaml" in paths
        assert "notes.yml" in paths
        # Non-importable files should be excluded
        assert "src/main.py" not in paths
        assert "logo.png" not in paths

    @pytest.mark.anyio
    async def test_list_tree_recursive_traversal(self):
        """Test that directories are traversed recursively."""
        adapter = _mock_adapter()
        # First call: root listing with a directory and a file
        root_resp = _resp(
            200,
            {
                "values": [
                    {"type": "commit_file", "path": "README.md", "size": 100, "commit": {"hash": "a1"}},
                    {"type": "commit_directory", "path": "docs"},
                ],
            },
        )
        # Second call: docs/ subdirectory listing
        docs_resp = _resp(
            200,
            {
                "values": [
                    {"type": "commit_file", "path": "docs/guide.md", "size": 200, "commit": {"hash": "b2"}},
                    {"type": "commit_directory", "path": "docs/api"},
                ],
            },
        )
        # Third call: docs/api/ subdirectory listing
        api_resp = _resp(
            200,
            {
                "values": [
                    {"type": "commit_file", "path": "docs/api/spec.yaml", "size": 300, "commit": {"hash": "c3"}},
                ],
            },
        )
        adapter._client.get = AsyncMock(side_effect=[root_resp, docs_resp, api_resp])

        entries = await adapter.list_tree("ws", "repo", "main")
        paths = [e.path for e in entries]
        assert "README.md" in paths
        assert "docs/guide.md" in paths
        assert "docs/api/spec.yaml" in paths
        assert len(entries) == 3

    @pytest.mark.anyio
    async def test_list_tree_entries_are_blobs(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            return_value=_resp(
                200,
                {
                    "values": [
                        {"type": "commit_file", "path": "README.md", "size": 100, "commit": {"hash": "a1"}},
                    ],
                },
            )
        )
        entries = await adapter.list_tree("ws", "repo", "main")
        assert len(entries) == 1
        assert all(isinstance(e, GitTreeEntry) for e in entries)
        assert entries[0].type == "blob"
        assert entries[0].sha == "a1"
        assert entries[0].size == 100

    @pytest.mark.anyio
    async def test_list_tree_root_url(self):
        """Root listing should use trailing slash (no path component)."""
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            return_value=_resp(200, {"values": []})
        )
        await adapter.list_tree("ws", "repo", "main")
        call_args = adapter._client.get.call_args
        assert call_args[0][0] == "/repositories/ws/repo/src/main/"

    @pytest.mark.anyio
    async def test_list_tree_missing_commit_hash(self):
        """Entries without a commit hash should default to empty string."""
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            return_value=_resp(
                200,
                {
                    "values": [
                        {"type": "commit_file", "path": "README.md", "size": 50},
                    ],
                },
            )
        )
        entries = await adapter.list_tree("ws", "repo", "main")
        assert entries[0].sha == ""


# ---------------------------------------------------------------------------
# get_file_content
# ---------------------------------------------------------------------------


class TestGetFileContent:
    @pytest.mark.anyio
    async def test_get_file_content_returns_raw_text(self):
        """Bitbucket returns raw content, not base64."""
        original = "# Hello World\n\nThis is a test."
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            side_effect=[
                # First call: raw content
                _resp(200, text=original),
                # Second call: metadata
                _resp(
                    200,
                    {
                        "commit": {"hash": "abc123"},
                        "size": len(original),
                        "path": "README.md",
                    },
                ),
            ]
        )
        fc = await adapter.get_file_content("ws", "repo", "README.md", ref="main")
        assert isinstance(fc, GitFileContent)
        assert fc.content == original
        assert fc.path == "README.md"
        assert fc.sha == "abc123"
        assert fc.size == len(original)

    @pytest.mark.anyio
    async def test_get_file_content_without_ref_defaults_to_main(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            side_effect=[
                _resp(200, text="content"),
                _resp(200, {"commit": {"hash": "xyz"}, "size": 7}),
            ]
        )
        fc = await adapter.get_file_content("ws", "repo", "data.json")
        assert fc.content == "content"
        # Verify the URL uses "main" as the default branch
        first_call = adapter._client.get.call_args_list[0]
        assert "/src/main/" in first_call[0][0]

    @pytest.mark.anyio
    async def test_get_file_content_meta_failure_graceful(self):
        """If the metadata request fails, sha defaults to empty and size to content length."""
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            side_effect=[
                _resp(200, text="some content"),
                _resp(404, {"error": "not found"}),
            ]
        )
        fc = await adapter.get_file_content("ws", "repo", "file.md", ref="develop")
        assert fc.content == "some content"
        assert fc.sha == ""
        assert fc.size == len("some content")

    @pytest.mark.anyio
    async def test_get_file_content_correct_urls(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            side_effect=[
                _resp(200, text="x"),
                _resp(200, {"commit": {"hash": "h"}, "size": 1}),
            ]
        )
        await adapter.get_file_content("ws", "repo", "docs/api/spec.yaml", ref="feature")
        # First call: raw content
        first_call = adapter._client.get.call_args_list[0]
        assert first_call[0][0] == "/repositories/ws/repo/src/feature/docs/api/spec.yaml"
        # Second call: metadata with format=meta
        second_call = adapter._client.get.call_args_list[1]
        assert second_call[0][0] == "/repositories/ws/repo/src/feature/docs/api/spec.yaml"
        assert second_call[1]["params"]["format"] == "meta"


# ---------------------------------------------------------------------------
# aclose
# ---------------------------------------------------------------------------


class TestAclose:
    @pytest.mark.anyio
    async def test_aclose_delegates_to_httpx(self):
        adapter = _mock_adapter()
        adapter._client.aclose = AsyncMock()
        await adapter.aclose()
        adapter._client.aclose.assert_awaited_once()


# ---------------------------------------------------------------------------
# _to_repo helper
# ---------------------------------------------------------------------------


class TestToRepoHelper:
    def test_to_repo_with_full_data(self):
        data = {
            "full_name": "ws/my-repo",
            "name": "my-repo",
            "is_private": True,
            "mainbranch": {"name": "develop"},
            "description": "A repo",
            "links": {"html": {"href": "https://bitbucket.org/ws/my-repo"}},
        }
        repo = BitbucketAdapter._to_repo(data)
        assert isinstance(repo, GitRepo)
        assert repo.full_name == "ws/my-repo"
        assert repo.name == "my-repo"
        assert repo.owner == "ws"
        assert repo.private is True
        assert repo.default_branch == "develop"
        assert repo.description == "A repo"
        assert repo.html_url == "https://bitbucket.org/ws/my-repo"

    def test_to_repo_with_minimal_data(self):
        data = {
            "full_name": "user/proj",
            "name": "proj",
            "is_private": False,
        }
        repo = BitbucketAdapter._to_repo(data)
        assert repo.full_name == "user/proj"
        assert repo.owner == "user"
        assert repo.private is False
        assert repo.default_branch == "main"  # default when no mainbranch
        assert repo.description == ""
        assert repo.html_url == ""

    def test_to_repo_null_description(self):
        data = {
            "full_name": "user/proj",
            "name": "proj",
            "is_private": False,
            "description": None,
            "mainbranch": {"name": "main"},
        }
        repo = BitbucketAdapter._to_repo(data)
        assert repo.description == ""

    def test_to_repo_null_mainbranch(self):
        data = {
            "full_name": "user/proj",
            "name": "proj",
            "is_private": False,
            "mainbranch": None,
        }
        repo = BitbucketAdapter._to_repo(data)
        assert repo.default_branch == "main"

    def test_to_repo_no_slash_in_full_name(self):
        data = {
            "full_name": "solo-repo",
            "name": "solo-repo",
            "is_private": False,
        }
        repo = BitbucketAdapter._to_repo(data)
        assert repo.owner == ""
