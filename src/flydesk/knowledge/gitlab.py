# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""GitLab REST API v4 client implementing the GitProvider protocol."""

from __future__ import annotations

import base64
import logging
import urllib.parse
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

logger = logging.getLogger(__name__)

IMPORTABLE_EXTENSIONS = {".md", ".json", ".yaml", ".yml"}


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class GitLabAdapter:
    """Adapts the GitLab REST API v4 to the :class:`~flydesk.knowledge.git_provider.GitProvider` protocol.

    Auth uses a ``PRIVATE-TOKEN`` header for Personal Access Tokens.
    The *base_url* defaults to ``https://gitlab.com`` but can be overridden
    for self-hosted instances.
    """

    provider_type: str = "gitlab"

    def __init__(
        self,
        token: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._base_url = (base_url or "https://gitlab.com").rstrip("/")
        api_base = f"{self._base_url}/api/v4"
        headers: dict[str, str] = {"Accept": "application/json"}
        if token:
            headers["PRIVATE-TOKEN"] = token
        self._client = httpx.AsyncClient(
            base_url=api_base,
            headers=headers,
            timeout=30.0,
        )

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _project_id(owner: str, repo: str) -> str:
        """Return the URL-encoded ``owner/repo`` path used by GitLab's API."""
        return urllib.parse.quote(f"{owner}/{repo}", safe="")

    @staticmethod
    def _to_repo(project: dict) -> GitRepo:
        """Convert a GitLab project JSON object to a :class:`GitRepo`."""
        namespace = project.get("namespace", {})
        path_with_ns = project.get("path_with_namespace", "")
        return GitRepo(
            full_name=path_with_ns,
            name=project.get("path", project.get("name", "")),
            owner=namespace.get("full_path", namespace.get("path", "")),
            private=project.get("visibility", "private") == "private",
            default_branch=project.get("default_branch", "main"),
            description=project.get("description") or "",
            html_url=project.get("web_url", ""),
        )

    # -- GitProvider interface ---------------------------------------------

    async def validate_token(self) -> bool:
        """Return *True* if the configured token is valid (``GET /user``)."""
        resp = await self._client.get("/user")
        return resp.status_code == 200

    async def list_accounts(self) -> list[GitAccount]:
        """List GitLab groups the authenticated user belongs to."""
        resp = await self._client.get(
            "/groups",
            params={"min_access_level": 10, "per_page": 100},
        )
        resp.raise_for_status()
        return [
            GitAccount(
                login=g["full_path"],
                avatar_url=g.get("avatar_url") or "",
                description=g.get("description") or "",
            )
            for g in resp.json()
        ]

    async def list_account_repos(
        self, account: str, search: str = ""
    ) -> list[GitRepo]:
        """List projects within a GitLab group (including subgroups)."""
        encoded = urllib.parse.quote(account, safe="")
        params: dict[str, str] = {
            "include_subgroups": "true",
            "per_page": "100",
        }
        if search:
            params["search"] = search
        resp = await self._client.get(
            f"/groups/{encoded}/projects",
            params=params,
        )
        resp.raise_for_status()
        return [self._to_repo(p) for p in resp.json()]

    async def list_user_repos(self, search: str = "") -> list[GitRepo]:
        """List projects the authenticated user is a member of."""
        params: dict[str, str] = {
            "membership": "true",
            "order_by": "updated_at",
            "per_page": "100",
        }
        if search:
            params["search"] = search
        resp = await self._client.get("/projects", params=params)
        resp.raise_for_status()
        return [self._to_repo(p) for p in resp.json()]

    async def list_branches(self, owner: str, repo: str) -> list[GitBranch]:
        """List branches for a GitLab project."""
        project_id = self._project_id(owner, repo)
        resp = await self._client.get(
            f"/projects/{project_id}/repository/branches",
            params={"per_page": 100},
        )
        resp.raise_for_status()
        return [
            GitBranch(name=b["name"], sha=b["commit"]["id"])
            for b in resp.json()
        ]

    async def list_tree(
        self, owner: str, repo: str, branch: str
    ) -> list[GitTreeEntry]:
        """Return the recursive file tree, filtered to importable extensions."""
        project_id = self._project_id(owner, repo)
        resp = await self._client.get(
            f"/projects/{project_id}/repository/tree",
            params={"recursive": "true", "ref": branch, "per_page": 100},
        )
        resp.raise_for_status()
        entries: list[GitTreeEntry] = []
        for item in resp.json():
            if item.get("type") != "blob":
                continue
            ext = PurePosixPath(item["path"]).suffix.lower()
            if ext in IMPORTABLE_EXTENSIONS:
                entries.append(
                    GitTreeEntry(
                        path=item["path"],
                        sha=item["id"],
                        size=0,
                        type="blob",
                    )
                )
        return entries

    async def get_file_content(
        self, owner: str, repo: str, path: str, ref: str | None = None
    ) -> GitFileContent:
        """Fetch and decode a single file from the repository."""
        project_id = self._project_id(owner, repo)
        encoded_path = urllib.parse.quote(path, safe="")
        params: dict[str, str] = {}
        if ref:
            params["ref"] = ref
        resp = await self._client.get(
            f"/projects/{project_id}/repository/files/{encoded_path}",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return GitFileContent(
            path=data.get("file_path", path),
            sha=data.get("blob_id", ""),
            content=content,
            size=data.get("size", 0),
        )

    async def aclose(self) -> None:
        """Release underlying HTTP resources."""
        await self._client.aclose()


# -- Register with the factory on import -----------------------------------

GitProviderFactory.register("gitlab", GitLabAdapter)
