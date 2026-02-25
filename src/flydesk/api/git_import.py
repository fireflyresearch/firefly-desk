# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Provider-agnostic Git import API.

Exposes a unified set of endpoints for browsing and importing content from
any configured Git provider (GitHub, GitLab, Bitbucket) via the
``GitProvider`` protocol and ``GitProviderFactory``.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from flydesk.api.git_providers import get_git_provider_repo
from flydesk.knowledge.git_provider import GitProvider, GitProviderFactory
from flydesk.knowledge.git_provider_repository import GitProviderRepository
from flydesk.rbac.guards import KnowledgeRead, KnowledgeWrite

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/git", tags=["git-import"])

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

Repo = Annotated[GitProviderRepository, Depends(get_git_provider_repo)]


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class RepoImportItem(BaseModel):
    """A single repository to import from the multi-repo cart."""

    owner: str
    repo: str
    branch: str
    paths: list[str]
    tags: list[str] = []


class MultiRepoImportRequest(BaseModel):
    """Multi-repo import request containing one or more repositories."""

    items: list[RepoImportItem]


class PreviewRequest(BaseModel):
    """Request to preview selected files before import."""

    branch: str
    paths: list[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_adapters_loaded(provider_type: str) -> None:
    """Import adapter modules so they register with the factory."""
    if provider_type == "github":
        import flydesk.knowledge.github  # noqa: F401
    elif provider_type == "gitlab":
        import flydesk.knowledge.gitlab  # noqa: F401
    elif provider_type == "bitbucket":
        import flydesk.knowledge.bitbucket  # noqa: F401


async def _make_provider(
    repo: GitProviderRepository, provider_id: str, token: str
) -> GitProvider:
    """Look up a Git provider from DB and instantiate the adapter."""
    row = await repo.get_provider(provider_id)
    if row is None or not row.is_active:
        raise HTTPException(404, "Git provider not found or inactive")
    # Ensure the adapter module is imported so factory knows the type
    _ensure_adapters_loaded(row.provider_type)
    return GitProviderFactory.create(row.provider_type, token=token, base_url=row.base_url)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/providers", dependencies=[KnowledgeRead])
async def list_git_providers(repo: Repo) -> list[dict]:
    """Return all active Git providers configured in the system."""
    rows = await repo.list_providers()
    return [
        {
            "id": r.id,
            "provider_type": r.provider_type,
            "display_name": r.display_name,
            "is_active": r.is_active,
        }
        for r in rows
        if r.is_active
    ]


@router.get("/{provider_id}/accounts", dependencies=[KnowledgeWrite])
async def list_accounts(provider_id: str, token: str, repo: Repo) -> list[dict]:
    """List organizations / groups / workspaces for the authenticated user."""
    provider = await _make_provider(repo, provider_id, token)
    try:
        accounts = await provider.list_accounts()
        return [
            {
                "login": a.login,
                "avatar_url": a.avatar_url,
                "description": a.description,
            }
            for a in accounts
        ]
    finally:
        await provider.aclose()


@router.get("/{provider_id}/repos", dependencies=[KnowledgeWrite])
async def list_repos(
    provider_id: str,
    token: str,
    repo: Repo,
    account: str | None = None,
    search: str = "",
) -> list[dict]:
    """List repositories for an account or the authenticated user."""
    provider = await _make_provider(repo, provider_id, token)
    try:
        if account:
            repos = await provider.list_account_repos(account, search=search)
        else:
            repos = await provider.list_user_repos(search=search)
        return [dataclasses.asdict(r) for r in repos]
    finally:
        await provider.aclose()


@router.get(
    "/{provider_id}/repos/{owner}/{repo_name}/branches",
    dependencies=[KnowledgeWrite],
)
async def list_branches(
    provider_id: str, owner: str, repo_name: str, token: str, repo: Repo
) -> list[dict]:
    """List branches for a repository."""
    provider = await _make_provider(repo, provider_id, token)
    try:
        branches = await provider.list_branches(owner, repo_name)
        return [dataclasses.asdict(b) for b in branches]
    finally:
        await provider.aclose()


@router.get(
    "/{provider_id}/repos/{owner}/{repo_name}/tree/{branch:path}",
    dependencies=[KnowledgeWrite],
)
async def list_tree(
    provider_id: str,
    owner: str,
    repo_name: str,
    branch: str,
    token: str,
    repo: Repo,
) -> list[dict]:
    """Return the recursive file tree for a branch."""
    provider = await _make_provider(repo, provider_id, token)
    try:
        entries = await provider.list_tree(owner, repo_name, branch)
        return [dataclasses.asdict(e) for e in entries]
    finally:
        await provider.aclose()


@router.post(
    "/{provider_id}/repos/{owner}/{repo_name}/preview",
    dependencies=[KnowledgeWrite],
)
async def preview_files(
    provider_id: str,
    owner: str,
    repo_name: str,
    body: PreviewRequest,
    token: str,
    repo: Repo,
) -> list[dict]:
    """Preview content of selected files before importing."""
    provider = await _make_provider(repo, provider_id, token)
    try:
        results = []
        for path in body.paths:
            try:
                content = await provider.get_file_content(
                    owner, repo_name, path, ref=body.branch
                )
                results.append(dataclasses.asdict(content))
            except Exception as exc:
                logger.warning(
                    "Failed to preview %s/%s:%s — %s", owner, repo_name, path, exc
                )
                results.append({"path": path, "error": str(exc)})
        return results
    finally:
        await provider.aclose()


@router.post("/{provider_id}/import", status_code=202, dependencies=[KnowledgeWrite])
async def import_repos(
    provider_id: str,
    token: str,
    body: MultiRepoImportRequest,
    repo: Repo,
) -> dict:
    """Accept a multi-repo import request (cart).

    For now this validates and returns ``202 Accepted`` with the queued items.
    Task 10 will wire this to the knowledge indexer for actual processing.
    """
    provider = await _make_provider(repo, provider_id, token)
    try:
        results = []
        for item in body.items:
            for path in item.paths:
                results.append(
                    {
                        "path": path,
                        "repo": f"{item.owner}/{item.repo}",
                        "status": "queued",
                    }
                )
        return {"status": "accepted", "items": results}
    finally:
        await provider.aclose()
