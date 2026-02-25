# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the unified GitProvider protocol, factory, and GitHubAdapter."""

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
from flydesk.knowledge.github import (
    GITHUB_API_BASE,
    GitHubAdapter,
    GitHubClient,
)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    """Verify GitHubAdapter satisfies the GitProvider protocol."""

    def test_github_adapter_is_git_provider(self):
        adapter = GitHubAdapter(token="ghp_test")
        assert isinstance(adapter, GitProvider)

    def test_provider_type_is_github(self):
        adapter = GitHubAdapter(token="ghp_test")
        assert adapter.provider_type == "github"

    def test_base_url_accepted_but_ignored(self):
        """base_url is accepted for interface symmetry but has no effect on GitHub."""
        adapter = GitHubAdapter(token="ghp_test", base_url="https://custom.example.com")
        assert adapter.provider_type == "github"
        # The underlying client still uses the standard GitHub API base
        assert str(adapter._client._client.base_url).rstrip("/") == GITHUB_API_BASE


# ---------------------------------------------------------------------------
# Factory tests
# ---------------------------------------------------------------------------


class TestGitProviderFactory:
    def test_factory_creates_github_adapter(self):
        provider = GitProviderFactory.create("github", token="ghp_test")
        assert isinstance(provider, GitHubAdapter)
        assert isinstance(provider, GitProvider)
        assert provider.provider_type == "github"

    def test_factory_rejects_unknown_provider(self):
        with pytest.raises(ValueError, match="Unsupported git provider"):
            GitProviderFactory.create("unknown_provider", token="tok")

    def test_factory_error_lists_registered_providers(self):
        with pytest.raises(ValueError, match="github"):
            GitProviderFactory.create("nope")

    def test_factory_register_and_create(self):
        """A custom adapter can be registered and retrieved."""

        class FakeAdapter:
            provider_type = "fake"

            def __init__(self, token=None, base_url=None):
                self.token = token

        GitProviderFactory.register("fake", FakeAdapter)
        try:
            provider = GitProviderFactory.create("fake", token="tok123")
            assert provider.provider_type == "fake"
            assert provider.token == "tok123"
        finally:
            # Clean up so this test doesn't leak state
            GitProviderFactory._registry.pop("fake", None)


# ---------------------------------------------------------------------------
# GitHubAdapter delegation tests
# ---------------------------------------------------------------------------


def _mock_github_client(token: str = "ghp_test") -> GitHubAdapter:
    """Return a GitHubAdapter whose internal client is fully mocked."""
    adapter = GitHubAdapter(token=token)
    adapter._client = AsyncMock(spec=GitHubClient)
    return adapter


class TestGitHubAdapterValidateToken:
    @pytest.mark.anyio
    async def test_validate_token_delegates(self):
        adapter = _mock_github_client()
        adapter._client.validate_token = AsyncMock(return_value=True)
        result = await adapter.validate_token()
        assert result is True
        adapter._client.validate_token.assert_awaited_once()

    @pytest.mark.anyio
    async def test_validate_token_false(self):
        adapter = _mock_github_client()
        adapter._client.validate_token = AsyncMock(return_value=False)
        result = await adapter.validate_token()
        assert result is False


class TestGitHubAdapterListAccounts:
    @pytest.mark.anyio
    async def test_list_accounts_maps_orgs(self):
        adapter = _mock_github_client()
        adapter._client.list_user_organizations = AsyncMock(
            return_value=[
                {"login": "firefly-org", "avatar_url": "https://img/1", "description": "Firefly"},
                {"login": "acme", "avatar_url": "", "description": ""},
            ]
        )
        accounts = await adapter.list_accounts()
        assert len(accounts) == 2
        assert all(isinstance(a, GitAccount) for a in accounts)
        assert accounts[0].login == "firefly-org"
        assert accounts[0].avatar_url == "https://img/1"
        assert accounts[1].login == "acme"


class TestGitHubAdapterListAccountRepos:
    @pytest.mark.anyio
    async def test_list_account_repos_delegates(self):
        from flydesk.knowledge.github import GitHubRepo

        adapter = _mock_github_client()
        adapter._client.list_org_repos = AsyncMock(
            return_value=[
                GitHubRepo(
                    full_name="org/repo1",
                    name="repo1",
                    owner="org",
                    private=False,
                    default_branch="main",
                ),
            ]
        )
        repos = await adapter.list_account_repos("org")
        assert len(repos) == 1
        assert isinstance(repos[0], GitRepo)
        assert repos[0].full_name == "org/repo1"

    @pytest.mark.anyio
    async def test_list_account_repos_filters_by_search(self):
        from flydesk.knowledge.github import GitHubRepo

        adapter = _mock_github_client()
        adapter._client.list_org_repos = AsyncMock(
            return_value=[
                GitHubRepo(
                    full_name="org/api-gateway",
                    name="api-gateway",
                    owner="org",
                    private=False,
                    default_branch="main",
                ),
                GitHubRepo(
                    full_name="org/web-app",
                    name="web-app",
                    owner="org",
                    private=False,
                    default_branch="main",
                ),
            ]
        )
        repos = await adapter.list_account_repos("org", search="api")
        assert len(repos) == 1
        assert repos[0].name == "api-gateway"


class TestGitHubAdapterListUserRepos:
    @pytest.mark.anyio
    async def test_list_user_repos_converts_types(self):
        from flydesk.knowledge.github import GitHubRepo

        adapter = _mock_github_client()
        adapter._client.list_user_repos = AsyncMock(
            return_value=[
                GitHubRepo(
                    full_name="user/my-repo",
                    name="my-repo",
                    owner="user",
                    private=True,
                    default_branch="develop",
                    description="My repo",
                    html_url="https://github.com/user/my-repo",
                ),
            ]
        )
        repos = await adapter.list_user_repos()
        assert len(repos) == 1
        r = repos[0]
        assert isinstance(r, GitRepo)
        assert r.full_name == "user/my-repo"
        assert r.private is True
        assert r.default_branch == "develop"
        assert r.html_url == "https://github.com/user/my-repo"

    @pytest.mark.anyio
    async def test_list_user_repos_with_search(self):
        from flydesk.knowledge.github import GitHubRepo

        adapter = _mock_github_client()
        adapter._client.list_user_repos = AsyncMock(
            return_value=[
                GitHubRepo(
                    full_name="user/alpha",
                    name="alpha",
                    owner="user",
                    private=False,
                    default_branch="main",
                ),
                GitHubRepo(
                    full_name="user/beta",
                    name="beta",
                    owner="user",
                    private=False,
                    default_branch="main",
                ),
            ]
        )
        repos = await adapter.list_user_repos(search="bet")
        assert len(repos) == 1
        assert repos[0].name == "beta"


class TestGitHubAdapterListBranches:
    @pytest.mark.anyio
    async def test_list_branches_converts_types(self):
        from flydesk.knowledge.github import GitHubBranch

        adapter = _mock_github_client()
        adapter._client.list_branches = AsyncMock(
            return_value=[
                GitHubBranch(name="main", sha="abc123"),
                GitHubBranch(name="develop", sha="def456"),
            ]
        )
        branches = await adapter.list_branches("owner", "repo")
        assert len(branches) == 2
        assert all(isinstance(b, GitBranch) for b in branches)
        assert branches[0].name == "main"
        assert branches[0].sha == "abc123"


class TestGitHubAdapterListTree:
    @pytest.mark.anyio
    async def test_list_tree_converts_types(self):
        from flydesk.knowledge.github import GitHubTreeEntry

        adapter = _mock_github_client()
        adapter._client.list_tree = AsyncMock(
            return_value=[
                GitHubTreeEntry(path="README.md", sha="a1", size=100, type="blob"),
                GitHubTreeEntry(path="config.yaml", sha="a2", size=50, type="blob"),
            ]
        )
        entries = await adapter.list_tree("owner", "repo", "main")
        assert len(entries) == 2
        assert all(isinstance(e, GitTreeEntry) for e in entries)
        assert entries[0].path == "README.md"
        assert entries[1].path == "config.yaml"


class TestGitHubAdapterGetFileContent:
    @pytest.mark.anyio
    async def test_get_file_content_converts_types(self):
        from flydesk.knowledge.github import GitHubFileContent

        adapter = _mock_github_client()
        adapter._client.get_file_content = AsyncMock(
            return_value=GitHubFileContent(
                path="README.md",
                sha="abc123",
                content="# Hello World",
                encoding="utf-8",
                size=13,
            )
        )
        fc = await adapter.get_file_content("owner", "repo", "README.md", ref="main")
        assert isinstance(fc, GitFileContent)
        assert fc.path == "README.md"
        assert fc.content == "# Hello World"
        assert fc.sha == "abc123"
        assert fc.size == 13
        adapter._client.get_file_content.assert_awaited_once_with(
            "owner", "repo", "README.md", ref="main"
        )


class TestGitHubAdapterAclose:
    @pytest.mark.anyio
    async def test_aclose_delegates(self):
        adapter = _mock_github_client()
        adapter._client.aclose = AsyncMock()
        await adapter.aclose()
        adapter._client.aclose.assert_awaited_once()


# ---------------------------------------------------------------------------
# Dataclass sanity checks
# ---------------------------------------------------------------------------


class TestUnifiedDataclasses:
    def test_git_account_defaults(self):
        acct = GitAccount(login="test")
        assert acct.avatar_url == ""
        assert acct.description == ""

    def test_git_repo_defaults(self):
        repo = GitRepo(
            full_name="o/r", name="r", owner="o", private=False, default_branch="main"
        )
        assert repo.description == ""
        assert repo.html_url == ""

    def test_git_branch(self):
        b = GitBranch(name="main", sha="abc")
        assert b.name == "main"

    def test_git_tree_entry_defaults(self):
        e = GitTreeEntry(path="file.md", sha="abc")
        assert e.size == 0
        assert e.type == "blob"

    def test_git_file_content_defaults(self):
        fc = GitFileContent(path="f.md", sha="abc", content="hello")
        assert fc.encoding == "utf-8"
        assert fc.size == 0
