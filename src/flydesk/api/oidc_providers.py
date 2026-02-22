# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""OIDC Provider Admin REST API -- CRUD for SSO provider configuration."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from flydesk.auth.repository import OIDCProviderRepository
from flydesk.models.oidc import OIDCProviderRow
from flydesk.rbac.guards import AdminSSO

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/oidc-providers", tags=["oidc-providers"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class OIDCProviderRequest(BaseModel):
    """Create or update an OIDC provider."""

    provider_type: str
    display_name: str
    issuer_url: str
    client_id: str
    client_secret: str | None = None
    tenant_id: str | None = None
    scopes: list[str] | None = None
    roles_claim: str | None = None
    permissions_claim: str | None = None
    is_active: bool = True


class OIDCProviderResponse(BaseModel):
    """Public representation of an OIDC provider (no secret)."""

    id: str
    provider_type: str
    display_name: str
    issuer_url: str
    client_id: str
    has_client_secret: bool
    tenant_id: str | None = None
    scopes: list[str] | None = None
    roles_claim: str | None = None
    permissions_claim: str | None = None
    is_active: bool = True
    created_at: str | None = None
    updated_at: str | None = None


class OIDCTestResult(BaseModel):
    """Result of an OIDC discovery test."""

    reachable: bool
    issuer: str | None = None
    authorization_endpoint: str | None = None
    token_endpoint: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_oidc_repo() -> OIDCProviderRepository:
    """Provide an OIDCProviderRepository instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_oidc_repo must be overridden via app.dependency_overrides"
    )


Repo = Annotated[OIDCProviderRepository, Depends(get_oidc_repo)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_response(row: OIDCProviderRow) -> OIDCProviderResponse:
    """Convert an ORM row to a response model with secret stripped."""
    return OIDCProviderResponse(
        id=row.id,
        provider_type=row.provider_type,
        display_name=row.display_name,
        issuer_url=row.issuer_url,
        client_id=row.client_id,
        has_client_secret=row.client_secret_encrypted is not None,
        tenant_id=row.tenant_id,
        scopes=_parse_scopes(row.scopes),
        roles_claim=row.roles_claim,
        permissions_claim=row.permissions_claim,
        is_active=row.is_active,
        created_at=row.created_at.isoformat() if row.created_at else None,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


def _parse_scopes(value: Any) -> list[str] | None:
    """Parse scopes which may be JSON string or list."""
    if value is None:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        import json

        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else None
        except (json.JSONDecodeError, TypeError):
            return None
    return None


# ---------------------------------------------------------------------------
# CRUD Endpoints
# ---------------------------------------------------------------------------


@router.get("", dependencies=[AdminSSO])
async def list_providers(repo: Repo) -> list[OIDCProviderResponse]:
    """Return every registered OIDC provider (secrets stripped)."""
    rows = await repo.list_providers()
    return [_to_response(r) for r in rows]


@router.post("", status_code=201, dependencies=[AdminSSO])
async def create_provider(
    body: OIDCProviderRequest, repo: Repo
) -> OIDCProviderResponse:
    """Register a new OIDC provider."""
    row = await repo.create_provider(
        provider_type=body.provider_type,
        display_name=body.display_name,
        issuer_url=body.issuer_url,
        client_id=body.client_id,
        client_secret=body.client_secret,
        tenant_id=body.tenant_id,
        scopes=body.scopes,
        roles_claim=body.roles_claim,
        permissions_claim=body.permissions_claim,
        is_active=body.is_active,
    )
    return _to_response(row)


@router.get("/{provider_id}", dependencies=[AdminSSO])
async def get_provider(provider_id: str, repo: Repo) -> OIDCProviderResponse:
    """Retrieve a single OIDC provider by ID (secret stripped)."""
    row = await repo.get_provider(provider_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")
    return _to_response(row)


@router.put("/{provider_id}", dependencies=[AdminSSO])
async def update_provider(
    provider_id: str, body: OIDCProviderRequest, repo: Repo
) -> OIDCProviderResponse:
    """Update an existing OIDC provider."""
    existing = await repo.get_provider(provider_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")

    kwargs: dict[str, Any] = {
        "provider_type": body.provider_type,
        "display_name": body.display_name,
        "issuer_url": body.issuer_url,
        "client_id": body.client_id,
        "tenant_id": body.tenant_id,
        "scopes": body.scopes,
        "roles_claim": body.roles_claim,
        "permissions_claim": body.permissions_claim,
        "is_active": body.is_active,
    }
    # Only update secret if provided (non-empty)
    if body.client_secret:
        kwargs["client_secret"] = body.client_secret

    updated = await repo.update_provider(provider_id, **kwargs)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")
    return _to_response(updated)


@router.delete("/{provider_id}", status_code=204, dependencies=[AdminSSO])
async def delete_provider(provider_id: str, repo: Repo) -> Response:
    """Remove an OIDC provider."""
    existing = await repo.get_provider(provider_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")
    await repo.delete_provider(provider_id)
    return Response(status_code=204)


@router.post("/{provider_id}/test", dependencies=[AdminSSO])
async def test_provider(provider_id: str, repo: Repo) -> OIDCTestResult:
    """Test OIDC discovery endpoint connectivity for a provider."""
    row = await repo.get_provider(provider_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")

    try:
        from flydesk.auth.oidc import OIDCClient

        client_secret = repo.decrypt_secret(row)
        client = OIDCClient(
            issuer_url=row.issuer_url,
            client_id=row.client_id,
            client_secret=client_secret or "",
        )
        discovery = await client.discover()
        return OIDCTestResult(
            reachable=True,
            issuer=discovery.issuer,
            authorization_endpoint=discovery.authorization_endpoint,
            token_endpoint=discovery.token_endpoint,
        )
    except Exception as exc:
        logger.warning("OIDC discovery test failed for %s: %s", provider_id, exc)
        return OIDCTestResult(
            reachable=False,
            error=str(exc),
        )


@router.post("/test-url", dependencies=[AdminSSO])
async def test_issuer_url(request: Request) -> OIDCTestResult:
    """Test OIDC discovery for an arbitrary issuer URL (before saving)."""
    body = await request.json()
    issuer_url = body.get("issuer_url", "")

    if not issuer_url:
        raise HTTPException(status_code=400, detail="issuer_url is required")

    try:
        from flydesk.auth.oidc import OIDCClient

        client = OIDCClient(
            issuer_url=issuer_url,
            client_id="test",
            client_secret="",
        )
        discovery = await client.discover()
        return OIDCTestResult(
            reachable=True,
            issuer=discovery.issuer,
            authorization_endpoint=discovery.authorization_endpoint,
            token_endpoint=discovery.token_endpoint,
        )
    except Exception as exc:
        logger.warning("OIDC discovery test failed for %s: %s", issuer_url, exc)
        return OIDCTestResult(
            reachable=False,
            error=str(exc),
        )
