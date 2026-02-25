# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""GitHub REST API v3 client for browsing and importing knowledge."""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field
from pathlib import PurePosixPath

import httpx

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
GITHUB_OAUTH_AUTHORIZE = "https://github.com/login/oauth/authorize"
GITHUB_OAUTH_ACCESS_TOKEN = "https://github.com/login/oauth/access_token"

IMPORTABLE_EXTENSIONS = {".md", ".json", ".yaml", ".yml"}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class GitHubRepo:
    """Lightweight representation of a GitHub repository."""

    full_name: str
    name: str
    owner: str
    private: bool
    default_branch: str
    description: str = ""
    html_url: str = ""


@dataclass
class GitHubBranch:
    """A branch in a GitHub repository."""

    name: str
    sha: str


@dataclass
class GitHubTreeEntry:
    """A single file entry from a recursive tree listing."""

    path: str
    sha: str
    size: int = 0
    type: str = "blob"


@dataclass
class GitHubFileContent:
    """Decoded content of a single file from the GitHub Contents API."""

    path: str
    sha: str
    content: str
    encoding: str = "utf-8"
    size: int = 0


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class GitHubClient:
    """Async wrapper around the GitHub REST API v3.

    Supports three auth modes:
      - **PAT** (Personal Access Token): ``Bearer <token>``
      - **OAuth**: same ``Bearer`` header after code exchange
      - **None**: public repositories only
    """

    def __init__(self, token: str | None = None) -> None:
        self._token = token
        headers: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(
            base_url=GITHUB_API_BASE,
            headers=headers,
            timeout=30.0,
        )

    @property
    def is_authenticated(self) -> bool:
        return self._token is not None

    async def aclose(self) -> None:
        await self._client.aclose()

    # -- Token validation ---------------------------------------------------

    async def validate_token(self) -> bool:
        """Return True if the token is valid (GET /user succeeds)."""
        if not self._token:
            return False
        resp = await self._client.get("/user")
        return resp.status_code == 200

    # -- Repos --------------------------------------------------------------

    async def list_user_repos(
        self, page: int = 1, per_page: int = 30
    ) -> list[GitHubRepo]:
        """List repositories for the authenticated user.

        Raises ``ValueError`` when called without a token.
        """
        if not self._token:
            raise ValueError("A token is required to list user repositories.")
        resp = await self._client.get(
            "/user/repos",
            params={"page": page, "per_page": per_page, "sort": "updated"},
        )
        resp.raise_for_status()
        return [_parse_repo(r) for r in resp.json()]

    async def search_repos(self, query: str) -> list[GitHubRepo]:
        """Search public repositories via the GitHub Search API."""
        resp = await self._client.get(
            "/search/repositories",
            params={"q": query, "per_page": 30},
        )
        resp.raise_for_status()
        return [_parse_repo(r) for r in resp.json().get("items", [])]

    # -- Organizations ------------------------------------------------------

    async def list_user_organizations(self) -> list[dict]:
        """List organizations the authenticated user belongs to."""
        if not self._token:
            raise ValueError("A token is required to list user organizations.")
        resp = await self._client.get("/user/orgs")
        resp.raise_for_status()
        return [
            {
                "login": o["login"],
                "avatar_url": o.get("avatar_url") or "",
                "description": o.get("description") or "",
            }
            for o in resp.json()
        ]

    async def list_org_repos(
        self, org: str, per_page: int = 30
    ) -> list[GitHubRepo]:
        """List repositories in a GitHub organization."""
        resp = await self._client.get(
            f"/orgs/{org}/repos",
            params={"per_page": per_page, "sort": "updated", "type": "all"},
        )
        resp.raise_for_status()
        return [_parse_repo(r) for r in resp.json()]

    # -- Branches -----------------------------------------------------------

    async def list_branches(
        self, owner: str, repo: str
    ) -> list[GitHubBranch]:
        """List branches for a repository."""
        resp = await self._client.get(
            f"/repos/{owner}/{repo}/branches",
            params={"per_page": 100},
        )
        resp.raise_for_status()
        return [
            GitHubBranch(name=b["name"], sha=b["commit"]["sha"])
            for b in resp.json()
        ]

    # -- Tree ---------------------------------------------------------------

    async def list_tree(
        self, owner: str, repo: str, branch: str
    ) -> list[GitHubTreeEntry]:
        """List the full recursive tree, filtered to importable file extensions."""
        resp = await self._client.get(
            f"/repos/{owner}/{repo}/git/trees/{branch}",
            params={"recursive": "1"},
        )
        resp.raise_for_status()
        entries: list[GitHubTreeEntry] = []
        for item in resp.json().get("tree", []):
            if item.get("type") != "blob":
                continue
            ext = PurePosixPath(item["path"]).suffix.lower()
            if ext in IMPORTABLE_EXTENSIONS:
                entries.append(
                    GitHubTreeEntry(
                        path=item["path"],
                        sha=item["sha"],
                        size=item.get("size", 0),
                        type=item["type"],
                    )
                )
        return entries

    # -- File content -------------------------------------------------------

    async def get_file_content(
        self, owner: str, repo: str, path: str, ref: str | None = None
    ) -> GitHubFileContent:
        """Fetch and decode a single file from the repository.

        The GitHub Contents API returns base64-encoded content.
        """
        params: dict[str, str] = {}
        if ref:
            params["ref"] = ref
        resp = await self._client.get(
            f"/repos/{owner}/{repo}/contents/{path}",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        raw_content = data.get("content", "")
        decoded = base64.b64decode(raw_content).decode("utf-8")
        return GitHubFileContent(
            path=data["path"],
            sha=data["sha"],
            content=decoded,
            size=data.get("size", 0),
        )


# ---------------------------------------------------------------------------
# OAuth code exchange (standalone function)
# ---------------------------------------------------------------------------


async def exchange_oauth_code(
    client_id: str, client_secret: str, code: str
) -> str:
    """Exchange an OAuth authorization code for an access token.

    Returns the access token string on success.
    Raises ``ValueError`` on failure.
    """
    async with httpx.AsyncClient() as http:
        resp = await http.post(
            GITHUB_OAUTH_ACCESS_TOKEN,
            json={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
    if "access_token" not in data:
        error = data.get("error_description", data.get("error", "unknown error"))
        raise ValueError(f"OAuth code exchange failed: {error}")
    return data["access_token"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_repo(data: dict) -> GitHubRepo:
    """Parse a repository JSON object from the GitHub API."""
    owner = data.get("owner", {})
    return GitHubRepo(
        full_name=data["full_name"],
        name=data["name"],
        owner=owner.get("login", ""),
        private=data.get("private", False),
        default_branch=data.get("default_branch", "main"),
        description=data.get("description") or "",
        html_url=data.get("html_url", ""),
    )


# ---------------------------------------------------------------------------
# GitProvider adapter
# ---------------------------------------------------------------------------


class GitHubAdapter:
    """Adapts :class:`GitHubClient` to the :class:`~flydesk.knowledge.git_provider.GitProvider` protocol.

    The adapter delegates every call to an underlying ``GitHubClient`` and
    converts GitHub-specific dataclasses to the unified types defined in
    :mod:`flydesk.knowledge.git_provider`.
    """

    provider_type: str = "github"

    def __init__(
        self,
        token: str | None = None,
        base_url: str | None = None,
    ) -> None:
        # base_url is accepted for interface symmetry but ignored --
        # GitHubClient always targets https://api.github.com.
        self._client = GitHubClient(token=token)

    # -- helpers to convert GitHub-specific types to unified types ----------

    @staticmethod
    def _to_repo(gh_repo: GitHubRepo) -> "git_provider.GitRepo":
        from flydesk.knowledge.git_provider import GitRepo

        return GitRepo(
            full_name=gh_repo.full_name,
            name=gh_repo.name,
            owner=gh_repo.owner,
            private=gh_repo.private,
            default_branch=gh_repo.default_branch,
            description=gh_repo.description,
            html_url=gh_repo.html_url,
        )

    @staticmethod
    def _to_branch(gh_branch: GitHubBranch) -> "git_provider.GitBranch":
        from flydesk.knowledge.git_provider import GitBranch

        return GitBranch(name=gh_branch.name, sha=gh_branch.sha)

    @staticmethod
    def _to_tree_entry(gh_entry: GitHubTreeEntry) -> "git_provider.GitTreeEntry":
        from flydesk.knowledge.git_provider import GitTreeEntry

        return GitTreeEntry(
            path=gh_entry.path,
            sha=gh_entry.sha,
            size=gh_entry.size,
            type=gh_entry.type,
        )

    @staticmethod
    def _to_file_content(gh_fc: GitHubFileContent) -> "git_provider.GitFileContent":
        from flydesk.knowledge.git_provider import GitFileContent

        return GitFileContent(
            path=gh_fc.path,
            sha=gh_fc.sha,
            content=gh_fc.content,
            encoding=gh_fc.encoding,
            size=gh_fc.size,
        )

    # -- GitProvider interface ---------------------------------------------

    async def validate_token(self) -> bool:
        return await self._client.validate_token()

    async def list_accounts(self) -> list[git_provider.GitAccount]:
        from flydesk.knowledge.git_provider import GitAccount

        orgs = await self._client.list_user_organizations()
        return [
            GitAccount(
                login=o["login"],
                avatar_url=o.get("avatar_url", ""),
                description=o.get("description", ""),
            )
            for o in orgs
        ]

    async def list_account_repos(
        self, account: str, search: str = ""
    ) -> list[git_provider.GitRepo]:
        gh_repos = await self._client.list_org_repos(account)
        repos = [self._to_repo(r) for r in gh_repos]
        if search:
            lower_search = search.lower()
            repos = [r for r in repos if lower_search in r.name.lower()]
        return repos

    async def list_user_repos(self, search: str = "") -> list[git_provider.GitRepo]:
        gh_repos = await self._client.list_user_repos()
        repos = [self._to_repo(r) for r in gh_repos]
        if search:
            lower_search = search.lower()
            repos = [r for r in repos if lower_search in r.name.lower()]
        return repos

    async def list_branches(self, owner: str, repo: str) -> list[git_provider.GitBranch]:
        gh_branches = await self._client.list_branches(owner, repo)
        return [self._to_branch(b) for b in gh_branches]

    async def list_tree(
        self, owner: str, repo: str, branch: str
    ) -> list[git_provider.GitTreeEntry]:
        gh_entries = await self._client.list_tree(owner, repo, branch)
        return [self._to_tree_entry(e) for e in gh_entries]

    async def get_file_content(
        self, owner: str, repo: str, path: str, ref: str | None = None
    ) -> git_provider.GitFileContent:
        gh_fc = await self._client.get_file_content(owner, repo, path, ref=ref)
        return self._to_file_content(gh_fc)

    async def aclose(self) -> None:
        await self._client.aclose()


# -- Register with the factory on import -----------------------------------

from flydesk.knowledge import git_provider  # noqa: E402

git_provider.GitProviderFactory.register("github", GitHubAdapter)
