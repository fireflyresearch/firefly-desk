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
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from flydesk.api.git_providers import get_git_provider_repo
from flydesk.api.knowledge import get_indexing_producer
from flydesk.knowledge.git_provider import GitProvider, GitProviderFactory
from flydesk.knowledge.git_provider_repository import GitProviderRepository
from flydesk.knowledge.queue import IndexingQueueProducer, IndexingTask
from flydesk.rbac.guards import KnowledgeRead, KnowledgeWrite

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/git", tags=["git-import"])

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

Repo = Annotated[GitProviderRepository, Depends(get_git_provider_repo)]
Producer = Annotated[IndexingQueueProducer, Depends(get_indexing_producer)]


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
    """Look up a Git provider from DB and instantiate the adapter.

    When ``token`` is the sentinel ``"stored"``, the encrypted PAT stored
    on the provider row is decrypted and used instead.
    """
    row = await repo.get_provider(provider_id)
    if row is None or not row.is_active:
        raise HTTPException(404, "Git provider not found or inactive")

    # Resolve stored PAT when sentinel value is passed
    effective_token = token
    if token == "stored" and row.auth_method == "pat":
        decrypted = repo.decrypt_secret(row)
        if not decrypted:
            raise HTTPException(400, "No stored token found for this provider")
        effective_token = decrypted

    # Ensure the adapter module is imported so factory knows the type
    _ensure_adapters_loaded(row.provider_type)
    return GitProviderFactory.create(row.provider_type, token=effective_token, base_url=row.base_url)


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
            "base_url": r.base_url,
            "auth_method": r.auth_method or "oauth",
            "has_client_secret": r.client_secret_encrypted is not None,
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
    producer: Producer,
) -> dict:
    """Accept a multi-repo import request (cart).

    Fetches file content from the Git provider and enqueues each file as an
    ``IndexingTask`` for background indexing by the knowledge queue consumer.
    """
    provider = await _make_provider(repo, provider_id, token)
    try:
        results = []
        for item in body.items:
            for path in item.paths:
                try:
                    fc = await provider.get_file_content(
                        item.owner, item.repo, path, ref=item.branch
                    )
                    task = IndexingTask(
                        document_id=str(uuid.uuid4()),
                        title=path.rsplit("/", 1)[-1].rsplit(".", 1)[0],
                        content=fc.content,
                        document_type="other",
                        source=f"git://{item.owner}/{item.repo}/{path}@{item.branch}",
                        tags=item.tags + ["git-import", f"repo:{item.owner}/{item.repo}"],
                        metadata={
                            "provider": provider_id,
                            "repo": f"{item.owner}/{item.repo}",
                            "branch": item.branch,
                            "path": path,
                            "sha": fc.sha,
                        },
                    )
                    await producer.enqueue(task)
                    results.append({"path": path, "document_id": task.document_id, "status": "queued"})
                except Exception as exc:
                    logger.warning(
                        "Failed to import %s/%s:%s — %s", item.owner, item.repo, path, exc
                    )
                    results.append({"path": path, "error": str(exc), "status": "failed"})
        return {"status": "accepted", "items": results}
    finally:
        await provider.aclose()
