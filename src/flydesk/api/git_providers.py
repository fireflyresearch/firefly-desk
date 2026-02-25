# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Git Provider Admin REST API -- CRUD for Git provider configuration."""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from flydesk.knowledge.git_provider_repository import GitProviderRepository
from flydesk.models.git_provider import GitProviderRow
from flydesk.rbac.guards import AdminGitProviders

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/git-providers", tags=["git-providers"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class GitProviderRequest(BaseModel):
    """Create or update a Git provider."""

    provider_type: str
    display_name: str
    base_url: str
    auth_method: str = "oauth"  # "oauth" or "pat"
    client_id: str | None = None
    client_secret: str | None = None  # OAuth client secret or PAT token
    oauth_authorize_url: str | None = None
    oauth_token_url: str | None = None
    scopes: list[str] | None = None
    is_active: bool = True


class GitProviderResponse(BaseModel):
    """Public representation of a Git provider (no secret)."""

    id: str
    provider_type: str
    display_name: str
    base_url: str
    auth_method: str = "oauth"
    client_id: str | None = None
    has_client_secret: bool
    oauth_authorize_url: str | None = None
    oauth_token_url: str | None = None
    scopes: list[str] | None = None
    is_active: bool = True
    created_at: str | None = None
    updated_at: str | None = None


class GitProviderTestResult(BaseModel):
    """Result of a Git provider connectivity test."""

    reachable: bool
    provider_type: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_git_provider_repo() -> GitProviderRepository:
    """Provide a GitProviderRepository instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_git_provider_repo must be overridden via app.dependency_overrides"
    )


Repo = Annotated[GitProviderRepository, Depends(get_git_provider_repo)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_response(row: GitProviderRow) -> GitProviderResponse:
    """Convert an ORM row to a response model with secret stripped."""
    return GitProviderResponse(
        id=row.id,
        provider_type=row.provider_type,
        display_name=row.display_name,
        base_url=row.base_url,
        auth_method=row.auth_method or "oauth",
        client_id=row.client_id,
        has_client_secret=row.client_secret_encrypted is not None,
        oauth_authorize_url=row.oauth_authorize_url,
        oauth_token_url=row.oauth_token_url,
        scopes=_parse_scopes(row.scopes),
        is_active=row.is_active,
        created_at=row.created_at.isoformat() if row.created_at else None,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


def _parse_json_list(value: Any) -> list[str] | None:
    """Parse a value that may be a JSON string or already a list."""
    if value is None:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else None
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def _parse_scopes(value: Any) -> list[str] | None:
    """Parse scopes which may be JSON string or list."""
    return _parse_json_list(value)


# ---------------------------------------------------------------------------
# CRUD Endpoints
# ---------------------------------------------------------------------------


@router.get("", dependencies=[AdminGitProviders])
async def list_providers(repo: Repo) -> list[GitProviderResponse]:
    """Return every registered Git provider (secrets stripped)."""
    rows = await repo.list_providers()
    return [_to_response(r) for r in rows]


@router.post("", status_code=201, dependencies=[AdminGitProviders])
async def create_provider(
    body: GitProviderRequest, repo: Repo
) -> GitProviderResponse:
    """Register a new Git provider."""
    row = await repo.create_provider(
        provider_type=body.provider_type,
        display_name=body.display_name,
        base_url=body.base_url,
        auth_method=body.auth_method,
        client_id=body.client_id,
        client_secret=body.client_secret,
        oauth_authorize_url=body.oauth_authorize_url,
        oauth_token_url=body.oauth_token_url,
        scopes=body.scopes,
        is_active=body.is_active,
    )
    return _to_response(row)


@router.get("/{provider_id}", dependencies=[AdminGitProviders])
async def get_provider(provider_id: str, repo: Repo) -> GitProviderResponse:
    """Retrieve a single Git provider by ID (secret stripped)."""
    row = await repo.get_provider(provider_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")
    return _to_response(row)


@router.put("/{provider_id}", dependencies=[AdminGitProviders])
async def update_provider(
    provider_id: str, body: GitProviderRequest, repo: Repo
) -> GitProviderResponse:
    """Update an existing Git provider."""
    existing = await repo.get_provider(provider_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")

    kwargs: dict[str, Any] = {
        "provider_type": body.provider_type,
        "display_name": body.display_name,
        "base_url": body.base_url,
        "auth_method": body.auth_method,
        "client_id": body.client_id,
        "oauth_authorize_url": body.oauth_authorize_url,
        "oauth_token_url": body.oauth_token_url,
        "scopes": body.scopes,
        "is_active": body.is_active,
    }
    # Only update secret if provided (non-empty)
    if body.client_secret:
        kwargs["client_secret"] = body.client_secret

    updated = await repo.update_provider(provider_id, **kwargs)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")
    return _to_response(updated)


@router.delete("/{provider_id}", status_code=204, dependencies=[AdminGitProviders])
async def delete_provider(provider_id: str, repo: Repo) -> Response:
    """Remove a Git provider."""
    existing = await repo.get_provider(provider_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")
    await repo.delete_provider(provider_id)
    return Response(status_code=204)


@router.post("/{provider_id}/test", dependencies=[AdminGitProviders])
async def test_provider(provider_id: str, repo: Repo) -> GitProviderTestResult:
    """Test Git provider connectivity by calling validate_token()."""
    row = await repo.get_provider(provider_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")

    try:
        from flydesk.knowledge.git_provider import GitProviderFactory

        client_secret = repo.decrypt_secret(row)
        provider = GitProviderFactory.create(
            provider_type=row.provider_type,
            token=client_secret or "",
            base_url=row.base_url,
        )
        try:
            valid = await provider.validate_token()
            return GitProviderTestResult(
                reachable=valid,
                provider_type=row.provider_type,
                error=None if valid else "Token validation failed",
            )
        finally:
            await provider.aclose()
    except Exception as exc:
        logger.warning("Git provider test failed for %s: %s", provider_id, exc)
        return GitProviderTestResult(
            reachable=False,
            provider_type=row.provider_type,
            error=str(exc),
        )
