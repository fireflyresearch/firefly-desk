# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the GitLab REST API v4 adapter (GitLabAdapter)."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock

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
from flydesk.knowledge.gitlab import GitLabAdapter


GITLAB_API_BASE = "https://gitlab.com/api/v4"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_adapter(
    token: str = "glpat-test",
    base_url: str | None = None,
) -> GitLabAdapter:
    """Return a GitLabAdapter with its internal httpx client mocked."""
    adapter = GitLabAdapter(token=token, base_url=base_url)
    adapter._client = AsyncMock(spec=httpx.AsyncClient)
    return adapter


def _resp(
    status: int,
    json_data: dict | list,
    method: str = "GET",
    url: str = GITLAB_API_BASE,
) -> httpx.Response:
    """Build a fake httpx.Response."""
    return httpx.Response(
        status,
        json=json_data,
        request=httpx.Request(method, url),
    )


# ---------------------------------------------------------------------------
# Construction / headers
# ---------------------------------------------------------------------------


class TestGitLabAdapterConstruction:
    def test_default_base_url(self):
        adapter = GitLabAdapter(token="glpat-test")
        assert str(adapter._client.base_url).rstrip("/") == GITLAB_API_BASE

    def test_custom_base_url(self):
        adapter = GitLabAdapter(token="glpat-test", base_url="https://gitlab.self-hosted.io")
        expected = "https://gitlab.self-hosted.io/api/v4"
        assert str(adapter._client.base_url).rstrip("/") == expected

    def test_trailing_slash_stripped(self):
        adapter = GitLabAdapter(token="glpat-test", base_url="https://gitlab.example.com/")
        expected = "https://gitlab.example.com/api/v4"
        assert str(adapter._client.base_url).rstrip("/") == expected

    def test_private_token_header_set(self):
        adapter = GitLabAdapter(token="glpat-abc")
        assert adapter._client.headers["PRIVATE-TOKEN"] == "glpat-abc"

    def test_no_token_no_auth_header(self):
        adapter = GitLabAdapter(token=None)
        assert "PRIVATE-TOKEN" not in adapter._client.headers

    def test_provider_type_is_gitlab(self):
        adapter = GitLabAdapter(token="glpat-test")
        assert adapter.provider_type == "gitlab"


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    def test_gitlab_adapter_is_git_provider(self):
        adapter = GitLabAdapter(token="glpat-test")
        assert isinstance(adapter, GitProvider)


# ---------------------------------------------------------------------------
# Factory registration
# ---------------------------------------------------------------------------


class TestFactoryRegistration:
    def test_factory_creates_gitlab_adapter(self):
        # Ensure the import triggered registration
        provider = GitProviderFactory.create("gitlab", token="glpat-test")
        assert isinstance(provider, GitLabAdapter)
        assert isinstance(provider, GitProvider)
        assert provider.provider_type == "gitlab"

    def test_factory_passes_base_url(self):
        provider = GitProviderFactory.create(
            "gitlab",
            token="glpat-test",
            base_url="https://gitlab.corp.example.com",
        )
        assert isinstance(provider, GitLabAdapter)
        expected = "https://gitlab.corp.example.com/api/v4"
        assert str(provider._client.base_url).rstrip("/") == expected


# ---------------------------------------------------------------------------
# validate_token
# ---------------------------------------------------------------------------


class TestValidateToken:
    @pytest.mark.anyio
    async def test_validate_token_success(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            return_value=_resp(200, {"id": 1, "username": "testuser"})
        )
        result = await adapter.validate_token()
        assert result is True
        adapter._client.get.assert_awaited_once_with("/user")

    @pytest.mark.anyio
    async def test_validate_token_unauthorized(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            return_value=_resp(401, {"message": "401 Unauthorized"})
        )
        result = await adapter.validate_token()
        assert result is False


# ---------------------------------------------------------------------------
# list_accounts (GitLab groups)
# ---------------------------------------------------------------------------


class TestListAccounts:
    @pytest.mark.anyio
    async def test_list_accounts_returns_groups(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            return_value=_resp(
                200,
                [
                    {
                        "id": 1,
                        "full_path": "firefly-org",
                        "avatar_url": "https://img/1",
                        "description": "Firefly Organization",
                    },
                    {
                        "id": 2,
                        "full_path": "acme/subgroup",
                        "avatar_url": None,
                        "description": None,
                    },
                ],
            )
        )
        accounts = await adapter.list_accounts()
        assert len(accounts) == 2
        assert all(isinstance(a, GitAccount) for a in accounts)
        assert accounts[0].login == "firefly-org"
        assert accounts[0].avatar_url == "https://img/1"
        assert accounts[0].description == "Firefly Organization"
        # None values should be converted to empty strings
        assert accounts[1].avatar_url == ""
        assert accounts[1].description == ""

    @pytest.mark.anyio
    async def test_list_accounts_passes_min_access_level(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(return_value=_resp(200, []))
        await adapter.list_accounts()
        adapter._client.get.assert_awaited_once_with(
            "/groups",
            params={"min_access_level": 10, "per_page": 100},
        )


# ---------------------------------------------------------------------------
# list_account_repos (group projects)
# ---------------------------------------------------------------------------


class TestListAccountRepos:
    @pytest.mark.anyio
    async def test_list_account_repos_success(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            return_value=_resp(
                200,
                [
                    {
                        "path_with_namespace": "firefly-org/api-gateway",
                        "path": "api-gateway",
                        "name": "API Gateway",
                        "namespace": {"full_path": "firefly-org", "path": "firefly-org"},
                        "visibility": "internal",
                        "default_branch": "main",
                        "description": "API Gateway service",
                        "web_url": "https://gitlab.com/firefly-org/api-gateway",
                    },
                    {
                        "path_with_namespace": "firefly-org/web-app",
                        "path": "web-app",
                        "name": "Web App",
                        "namespace": {"full_path": "firefly-org", "path": "firefly-org"},
                        "visibility": "private",
                        "default_branch": "develop",
                        "description": "Frontend",
                        "web_url": "https://gitlab.com/firefly-org/web-app",
                    },
                ],
            )
        )
        repos = await adapter.list_account_repos("firefly-org")
        assert len(repos) == 2
        assert all(isinstance(r, GitRepo) for r in repos)
        assert repos[0].full_name == "firefly-org/api-gateway"
        assert repos[0].name == "api-gateway"
        assert repos[0].owner == "firefly-org"
        assert repos[0].private is False  # "internal" != "private"
        assert repos[1].private is True
        assert repos[1].default_branch == "develop"

    @pytest.mark.anyio
    async def test_list_account_repos_with_search(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(return_value=_resp(200, []))
        await adapter.list_account_repos("firefly-org", search="api")
        adapter._client.get.assert_awaited_once()
        call_args = adapter._client.get.call_args
        assert call_args[1]["params"]["search"] == "api"
        assert call_args[1]["params"]["include_subgroups"] == "true"

    @pytest.mark.anyio
    async def test_list_account_repos_url_encodes_group(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(return_value=_resp(200, []))
        await adapter.list_account_repos("acme/subgroup")
        call_args = adapter._client.get.call_args
        # The group path should be URL-encoded in the URL
        assert call_args[0][0] == "/groups/acme%2Fsubgroup/projects"


# ---------------------------------------------------------------------------
# list_user_repos
# ---------------------------------------------------------------------------


class TestListUserRepos:
    @pytest.mark.anyio
    async def test_list_user_repos_success(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            return_value=_resp(
                200,
                [
                    {
                        "path_with_namespace": "user/my-project",
                        "path": "my-project",
                        "name": "My Project",
                        "namespace": {"full_path": "user", "path": "user"},
                        "visibility": "public",
                        "default_branch": "main",
                        "description": "My project",
                        "web_url": "https://gitlab.com/user/my-project",
                    },
                ],
            )
        )
        repos = await adapter.list_user_repos()
        assert len(repos) == 1
        r = repos[0]
        assert isinstance(r, GitRepo)
        assert r.full_name == "user/my-project"
        assert r.name == "my-project"
        assert r.owner == "user"
        assert r.private is False  # "public" != "private"
        assert r.html_url == "https://gitlab.com/user/my-project"

    @pytest.mark.anyio
    async def test_list_user_repos_with_search(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(return_value=_resp(200, []))
        await adapter.list_user_repos(search="tool")
        call_args = adapter._client.get.call_args
        assert call_args[1]["params"]["search"] == "tool"
        assert call_args[1]["params"]["membership"] == "true"

    @pytest.mark.anyio
    async def test_list_user_repos_no_search_omits_param(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(return_value=_resp(200, []))
        await adapter.list_user_repos()
        call_args = adapter._client.get.call_args
        assert "search" not in call_args[1]["params"]


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
                [
                    {"name": "main", "commit": {"id": "abc123"}},
                    {"name": "develop", "commit": {"id": "def456"}},
                ],
            )
        )
        branches = await adapter.list_branches("firefly-org", "api-gateway")
        assert len(branches) == 2
        assert all(isinstance(b, GitBranch) for b in branches)
        assert branches[0].name == "main"
        assert branches[0].sha == "abc123"
        assert branches[1].name == "develop"
        assert branches[1].sha == "def456"

    @pytest.mark.anyio
    async def test_list_branches_url_encodes_project(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(return_value=_resp(200, []))
        await adapter.list_branches("firefly-org", "api-gateway")
        call_args = adapter._client.get.call_args
        assert call_args[0][0] == "/projects/firefly-org%2Fapi-gateway/repository/branches"


# ---------------------------------------------------------------------------
# list_tree
# ---------------------------------------------------------------------------


class TestListTree:
    @pytest.mark.anyio
    async def test_list_tree_filters_importable(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            return_value=_resp(
                200,
                [
                    {"path": "README.md", "id": "a1", "type": "blob"},
                    {"path": "src/main.py", "id": "a2", "type": "blob"},
                    {"path": "docs/guide.yaml", "id": "a3", "type": "blob"},
                    {"path": "config.json", "id": "a4", "type": "blob"},
                    {"path": "notes.yml", "id": "a5", "type": "blob"},
                    {"path": "src", "id": "a6", "type": "tree"},
                    {"path": "logo.png", "id": "a7", "type": "blob"},
                ],
            )
        )
        entries = await adapter.list_tree("org", "repo", "main")
        paths = [e.path for e in entries]
        assert "README.md" in paths
        assert "docs/guide.yaml" in paths
        assert "config.json" in paths
        assert "notes.yml" in paths
        # Non-importable files should be excluded
        assert "src/main.py" not in paths
        assert "logo.png" not in paths
        # Directories should be excluded
        assert "src" not in paths

    @pytest.mark.anyio
    async def test_list_tree_all_entries_are_blobs(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            return_value=_resp(
                200,
                [
                    {"path": "README.md", "id": "a1", "type": "blob"},
                ],
            )
        )
        entries = await adapter.list_tree("org", "repo", "main")
        assert len(entries) == 1
        assert all(isinstance(e, GitTreeEntry) for e in entries)
        assert entries[0].type == "blob"
        assert entries[0].size == 0  # GitLab tree doesn't return size

    @pytest.mark.anyio
    async def test_list_tree_passes_ref_param(self):
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(return_value=_resp(200, []))
        await adapter.list_tree("org", "repo", "feature/test")
        call_args = adapter._client.get.call_args
        assert call_args[1]["params"]["ref"] == "feature/test"
        assert call_args[1]["params"]["recursive"] == "true"


# ---------------------------------------------------------------------------
# get_file_content
# ---------------------------------------------------------------------------


class TestGetFileContent:
    @pytest.mark.anyio
    async def test_get_file_content_decodes_base64(self):
        original = "# Hello World\n\nThis is a test."
        encoded = base64.b64encode(original.encode()).decode()
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            return_value=_resp(
                200,
                {
                    "file_path": "README.md",
                    "blob_id": "abc123",
                    "content": encoded,
                    "size": len(original),
                    "encoding": "base64",
                },
            )
        )
        fc = await adapter.get_file_content("org", "repo", "README.md", ref="main")
        assert isinstance(fc, GitFileContent)
        assert fc.content == original
        assert fc.path == "README.md"
        assert fc.sha == "abc123"
        assert fc.size == len(original)

    @pytest.mark.anyio
    async def test_get_file_content_without_ref(self):
        encoded = base64.b64encode(b"content").decode()
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            return_value=_resp(
                200,
                {
                    "file_path": "data.json",
                    "blob_id": "xyz789",
                    "content": encoded,
                    "size": 7,
                },
            )
        )
        fc = await adapter.get_file_content("org", "repo", "data.json")
        assert fc.content == "content"
        # Verify no ref param was sent
        call_args = adapter._client.get.call_args
        assert call_args[1]["params"] == {}

    @pytest.mark.anyio
    async def test_get_file_content_url_encodes_path(self):
        encoded = base64.b64encode(b"x").decode()
        adapter = _mock_adapter()
        adapter._client.get = AsyncMock(
            return_value=_resp(
                200,
                {"file_path": "docs/api/spec.yaml", "blob_id": "a", "content": encoded, "size": 1},
            )
        )
        await adapter.get_file_content("org", "repo", "docs/api/spec.yaml", ref="main")
        call_args = adapter._client.get.call_args
        url = call_args[0][0]
        assert "docs%2Fapi%2Fspec.yaml" in url


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
        project = {
            "path_with_namespace": "org/my-repo",
            "path": "my-repo",
            "name": "My Repo",
            "namespace": {"full_path": "org", "path": "org"},
            "visibility": "private",
            "default_branch": "develop",
            "description": "A repo",
            "web_url": "https://gitlab.com/org/my-repo",
        }
        repo = GitLabAdapter._to_repo(project)
        assert isinstance(repo, GitRepo)
        assert repo.full_name == "org/my-repo"
        assert repo.name == "my-repo"
        assert repo.owner == "org"
        assert repo.private is True
        assert repo.default_branch == "develop"
        assert repo.description == "A repo"
        assert repo.html_url == "https://gitlab.com/org/my-repo"

    def test_to_repo_with_minimal_data(self):
        project = {
            "path_with_namespace": "user/proj",
            "path": "proj",
            "name": "proj",
            "namespace": {"path": "user"},
            "visibility": "public",
        }
        repo = GitLabAdapter._to_repo(project)
        assert repo.full_name == "user/proj"
        assert repo.owner == "user"
        assert repo.private is False
        assert repo.default_branch == "main"
        assert repo.description == ""
        assert repo.html_url == ""

    def test_to_repo_null_description(self):
        project = {
            "path_with_namespace": "user/proj",
            "path": "proj",
            "name": "proj",
            "namespace": {"full_path": "user"},
            "visibility": "public",
            "description": None,
        }
        repo = GitLabAdapter._to_repo(project)
        assert repo.description == ""
