# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""GitHub browsing and import API routes."""

from __future__ import annotations

import logging
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Annotated
from urllib.parse import urlencode

if TYPE_CHECKING:
    from flydesk.knowledge.analyzer import DocumentAnalyzer

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from flydesk.config import DeskConfig, get_config
from flydesk.knowledge.github import (
    GITHUB_OAUTH_AUTHORIZE,
    IMPORTABLE_EXTENSIONS,
    GitHubClient,
    exchange_oauth_code,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/github", tags=["github"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class OAuthURLResponse(BaseModel):
    """Response containing the GitHub OAuth authorization URL."""

    url: str


class OAuthCallbackResponse(BaseModel):
    """Response after a successful OAuth code exchange."""

    access_token: str


class RepoResponse(BaseModel):
    full_name: str
    name: str
    owner: str
    private: bool
    default_branch: str
    description: str = ""
    html_url: str = ""


class BranchResponse(BaseModel):
    name: str
    sha: str


class TreeEntryResponse(BaseModel):
    path: str
    sha: str
    size: int = 0
    file_type: str = "unknown"


class PreviewRequest(BaseModel):
    """Request body for previewing files before import."""

    paths: list[str]
    branch: str = "main"


class PreviewFileResponse(BaseModel):
    path: str
    file_type: str
    size: int = 0
    content_preview: str = ""


class ImportRequest(BaseModel):
    """Request body for importing files from a GitHub repository."""

    paths: list[str]
    branch: str = "main"
    tags: list[str] = Field(default_factory=list)


class ImportAcceptedResponse(BaseModel):
    """Response when an import job has been accepted."""

    status: str = "accepted"
    files: int = 0


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


Config = Annotated[DeskConfig, Depends(get_config)]


def get_document_analyzer() -> DocumentAnalyzer:
    """FastAPI dependency stub -- overridden in server lifespan."""
    raise NotImplementedError


def _make_client(token: str | None = None) -> GitHubClient:
    """Create a GitHubClient with the given token."""
    return GitHubClient(token=token)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _classify_file(path: str) -> str:
    """Classify a file path into a content type for the knowledge base.

    Returns one of: ``markdown``, ``openapi``, ``data``, ``unknown``.
    """
    ext = PurePosixPath(path).suffix.lower()
    name_lower = PurePosixPath(path).name.lower()
    if ext == ".md":
        return "markdown"
    if ext in {".json", ".yaml", ".yml"}:
        # Heuristic: files with "openapi" or "swagger" in the name are specs
        if "openapi" in name_lower or "swagger" in name_lower:
            return "openapi"
        return "data"
    return "unknown"


# ---------------------------------------------------------------------------
# OAuth routes
# ---------------------------------------------------------------------------


@router.get("/auth/url")
async def get_oauth_url(config: Config) -> OAuthURLResponse:
    """Return the GitHub OAuth authorization URL for the configured app."""
    if not config.github_client_id:
        raise HTTPException(
            status_code=501,
            detail="GitHub OAuth is not configured (FLYDESK_GITHUB_CLIENT_ID is empty).",
        )
    params = {
        "client_id": config.github_client_id,
        "scope": "repo",
    }
    url = f"{GITHUB_OAUTH_AUTHORIZE}?{urlencode(params)}"
    return OAuthURLResponse(url=url)


@router.get("/auth/callback")
async def oauth_callback(
    config: Config,
    code: str = Query(..., description="GitHub OAuth authorization code"),
) -> OAuthCallbackResponse:
    """Exchange a GitHub OAuth authorization code for an access token."""
    if not config.github_client_id or not config.github_client_secret:
        raise HTTPException(
            status_code=501, detail="GitHub OAuth is not configured."
        )
    try:
        access_token = await exchange_oauth_code(
            config.github_client_id, config.github_client_secret, code
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"GitHub API error: {exc.response.text}",
        )
    return OAuthCallbackResponse(access_token=access_token)


# ---------------------------------------------------------------------------
# Repo browsing routes
# ---------------------------------------------------------------------------


@router.get("/repos")
async def list_repos(
    token: str | None = Query(default=None, description="GitHub PAT or OAuth token"),
    search: str | None = Query(default=None, description="Search query for public repos"),
) -> list[RepoResponse]:
    """List authenticated user's repos or search public repos."""
    if not token and not search:
        raise HTTPException(
            status_code=400,
            detail="Provide a token (for your repos) or a search query (for public repos).",
        )
    client = _make_client(token)
    try:
        if token and not search:
            repos = await client.list_user_repos()
        else:
            repos = await client.search_repos(search or "")
        return [
            RepoResponse(
                full_name=r.full_name,
                name=r.name,
                owner=r.owner,
                private=r.private,
                default_branch=r.default_branch,
                description=r.description,
                html_url=r.html_url,
            )
            for r in repos
        ]
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"GitHub API error: {exc.response.text}",
        )
    finally:
        await client.aclose()


@router.get("/repos/{owner}/{repo}/branches")
async def list_branches(
    owner: str,
    repo: str,
    token: str | None = Query(default=None),
) -> list[BranchResponse]:
    """List branches for a repository."""
    client = _make_client(token)
    try:
        branches = await client.list_branches(owner, repo)
        return [BranchResponse(name=b.name, sha=b.sha) for b in branches]
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"GitHub API error: {exc.response.text}",
        )
    finally:
        await client.aclose()


@router.get("/repos/{owner}/{repo}/tree/{branch:path}")
async def list_tree(
    owner: str,
    repo: str,
    branch: str,
    token: str | None = Query(default=None),
) -> list[TreeEntryResponse]:
    """List importable files in a repository tree."""
    client = _make_client(token)
    try:
        entries = await client.list_tree(owner, repo, branch)
        return [
            TreeEntryResponse(
                path=e.path,
                sha=e.sha,
                size=e.size,
                file_type=_classify_file(e.path),
            )
            for e in entries
        ]
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"GitHub API error: {exc.response.text}",
        )
    finally:
        await client.aclose()


# ---------------------------------------------------------------------------
# Preview / Import routes
# ---------------------------------------------------------------------------


@router.post("/repos/{owner}/{repo}/preview")
async def preview_files(
    owner: str,
    repo: str,
    body: PreviewRequest,
    token: str | None = Query(default=None),
) -> list[PreviewFileResponse]:
    """Preview the content of selected files before importing."""
    client = _make_client(token)
    try:
        results: list[PreviewFileResponse] = []
        for path in body.paths:
            try:
                fc = await client.get_file_content(owner, repo, path, ref=body.branch)
                preview = fc.content[:500] if len(fc.content) > 500 else fc.content
                results.append(
                    PreviewFileResponse(
                        path=fc.path,
                        file_type=_classify_file(fc.path),
                        size=fc.size,
                        content_preview=preview,
                    )
                )
            except httpx.HTTPStatusError:
                logger.warning("Could not fetch %s for preview.", path)
        return results
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"GitHub API error: {exc.response.text}",
        )
    finally:
        await client.aclose()


@router.post("/repos/{owner}/{repo}/import", status_code=202)
async def import_files(
    owner: str,
    repo: str,
    body: ImportRequest,
    token: str | None = Query(default=None),
) -> ImportAcceptedResponse:
    """Import selected files from a GitHub repository into the knowledge base.

    This is a placeholder -- the actual indexing will be wired in a later task.
    """
    # TODO: Wire to knowledge importer / indexing queue
    return ImportAcceptedResponse(status="accepted", files=len(body.paths))
