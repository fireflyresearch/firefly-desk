# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Bitbucket Cloud REST API 2.0 client implementing the GitProvider protocol."""

from __future__ import annotations

import logging
from pathlib import PurePosixPath

import httpx

from flydesk.knowledge.git_provider import (
    GitAccount,
    GitBranch,
    GitFileContent,
    GitProviderFactory,
    GitRepo,
    GitTreeEntry,
)
from flydesk.knowledge.github import IMPORTABLE_EXTENSIONS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class BitbucketAdapter:
    """Adapts the Bitbucket Cloud REST API 2.0 to the
    :class:`~flydesk.knowledge.git_provider.GitProvider` protocol.

    Auth uses ``Authorization: Bearer <token>`` headers.
    The *base_url* defaults to ``https://api.bitbucket.org/2.0`` but can be
    overridden for Bitbucket Data Center instances.
    """

    provider_type: str = "bitbucket"

    def __init__(
        self,
        token: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._base_url = (base_url or "https://api.bitbucket.org/2.0").rstrip("/")
        headers: dict[str, str] = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=30.0,
        )

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _to_repo(data: dict) -> GitRepo:
        """Convert a Bitbucket repository JSON object to a :class:`GitRepo`."""
        full_name = data.get("full_name", "")
        return GitRepo(
            full_name=full_name,
            name=data.get("name", ""),
            owner=full_name.split("/")[0] if "/" in full_name else "",
            private=data.get("is_private", False),
            default_branch=(
                data.get("mainbranch", {}).get("name", "main")
                if data.get("mainbranch")
                else "main"
            ),
            description=data.get("description") or "",
            html_url=data.get("links", {}).get("html", {}).get("href", ""),
        )

    # -- GitProvider interface ---------------------------------------------

    async def validate_token(self) -> bool:
        """Return *True* if the configured token is valid (``GET /user``)."""
        resp = await self._client.get("/user")
        return resp.status_code == 200

    async def list_accounts(self) -> list[GitAccount]:
        """List Bitbucket workspaces the authenticated user belongs to."""
        resp = await self._client.get(
            "/workspaces",
            params={"pagelen": 100},
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            GitAccount(
                login=w["slug"],
                avatar_url=w.get("links", {}).get("avatar", {}).get("href", ""),
                description=w.get("name") or "",
            )
            for w in data.get("values", [])
        ]

    async def list_account_repos(
        self, account: str, search: str = ""
    ) -> list[GitRepo]:
        """List repositories within a Bitbucket workspace."""
        params: dict[str, str | int] = {"pagelen": 100}
        if search:
            params["q"] = f'name~"{search}"'
        resp = await self._client.get(
            f"/repositories/{account}",
            params=params,
        )
        resp.raise_for_status()
        return [self._to_repo(r) for r in resp.json().get("values", [])]

    async def list_user_repos(self, search: str = "") -> list[GitRepo]:
        """List repositories the authenticated user is a member of."""
        user_resp = await self._client.get("/user")
        user_resp.raise_for_status()
        username = user_resp.json().get("username", "")
        params: dict[str, str | int] = {"role": "member", "pagelen": 100}
        if search:
            params["q"] = f'name~"{search}"'
        resp = await self._client.get(
            f"/repositories/{username}",
            params=params,
        )
        resp.raise_for_status()
        return [self._to_repo(r) for r in resp.json().get("values", [])]

    async def list_branches(self, owner: str, repo: str) -> list[GitBranch]:
        """List branches for a Bitbucket repository."""
        resp = await self._client.get(
            f"/repositories/{owner}/{repo}/refs/branches",
            params={"pagelen": 100},
        )
        resp.raise_for_status()
        return [
            GitBranch(name=b["name"], sha=b["target"]["hash"])
            for b in resp.json().get("values", [])
        ]

    async def list_tree(
        self, owner: str, repo: str, branch: str
    ) -> list[GitTreeEntry]:
        """Return the recursive file tree, filtered to importable extensions.

        Bitbucket has no recursive tree endpoint, so we traverse directories
        manually.
        """
        entries: list[GitTreeEntry] = []
        await self._traverse_directory(owner, repo, branch, "", entries)
        return entries

    async def _traverse_directory(
        self,
        owner: str,
        repo: str,
        branch: str,
        path: str,
        entries: list[GitTreeEntry],
    ) -> None:
        """Recursively fetch directory contents from the Bitbucket source API."""
        url_path = (
            f"/repositories/{owner}/{repo}/src/{branch}/{path}"
            if path
            else f"/repositories/{owner}/{repo}/src/{branch}/"
        )
        resp = await self._client.get(url_path, params={"pagelen": 100})
        resp.raise_for_status()
        for item in resp.json().get("values", []):
            if item.get("type") == "commit_directory":
                await self._traverse_directory(
                    owner, repo, branch, item["path"], entries
                )
            elif item.get("type") == "commit_file":
                ext = PurePosixPath(item["path"]).suffix.lower()
                if ext in IMPORTABLE_EXTENSIONS:
                    entries.append(
                        GitTreeEntry(
                            path=item["path"],
                            sha=item.get("commit", {}).get("hash", ""),
                            size=item.get("size", 0),
                            type="blob",
                        )
                    )

    async def get_file_content(
        self, owner: str, repo: str, path: str, ref: str | None = None
    ) -> GitFileContent:
        """Fetch a single file from the repository.

        Bitbucket returns raw content (not base64-encoded).  A second request
        with ``?format=meta`` retrieves the commit hash and size metadata.
        """
        branch = ref or "main"
        resp = await self._client.get(
            f"/repositories/{owner}/{repo}/src/{branch}/{path}",
        )
        resp.raise_for_status()
        content = resp.text

        # Fetch metadata (commit hash, size)
        meta_resp = await self._client.get(
            f"/repositories/{owner}/{repo}/src/{branch}/{path}",
            params={"format": "meta"},
        )
        sha = ""
        size = len(content)
        if meta_resp.status_code == 200:
            meta = meta_resp.json()
            sha = meta.get("commit", {}).get("hash", "")
            size = meta.get("size", size)

        return GitFileContent(
            path=path,
            sha=sha,
            content=content,
            size=size,
        )

    async def aclose(self) -> None:
        """Release underlying HTTP resources."""
        await self._client.aclose()


# -- Register with the factory on import -----------------------------------

GitProviderFactory.register("bitbucket", BitbucketAdapter)
