# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""LLM Provider Admin REST API -- CRUD for LLM provider configuration."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from flydek.llm.health import LLMHealthChecker
from flydek.llm.models import LLMProvider, LLMProviderResponse, ProviderHealthStatus
from flydek.llm.repository import LLMProviderRepository

router = APIRouter(prefix="/api/admin/llm-providers", tags=["llm-providers"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_llm_repo() -> LLMProviderRepository:
    """Provide an LLMProviderRepository instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_llm_repo must be overridden via app.dependency_overrides"
    )


async def _require_admin(request: Request) -> None:
    """Raise 403 unless the authenticated user has the 'admin' role."""
    user = getattr(request.state, "user_session", None)
    if user is None or "admin" not in user.roles:
        raise HTTPException(status_code=403, detail="Admin role required")


AdminGuard = Depends(_require_admin)
Repo = Annotated[LLMProviderRepository, Depends(get_llm_repo)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_response(provider: LLMProvider) -> LLMProviderResponse:
    """Convert a domain provider to a response model with api_key stripped."""
    return LLMProviderResponse(
        id=provider.id,
        name=provider.name,
        provider_type=provider.provider_type,
        base_url=provider.base_url,
        models=provider.models,
        default_model=provider.default_model,
        capabilities=provider.capabilities,
        config=provider.config,
        is_default=provider.is_default,
        is_active=provider.is_active,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
        has_api_key=provider.api_key is not None and len(provider.api_key) > 0,
    )


# ---------------------------------------------------------------------------
# CRUD Endpoints
# ---------------------------------------------------------------------------


@router.get("", dependencies=[AdminGuard])
async def list_providers(repo: Repo) -> list[LLMProviderResponse]:
    """Return every registered LLM provider (API keys stripped)."""
    providers = await repo.list_providers()
    return [_to_response(p) for p in providers]


@router.post("", status_code=201, dependencies=[AdminGuard])
async def create_provider(provider: LLMProvider, repo: Repo) -> LLMProviderResponse:
    """Register a new LLM provider."""
    await repo.create_provider(provider)
    return _to_response(provider)


@router.get("/{provider_id}", dependencies=[AdminGuard])
async def get_provider(provider_id: str, repo: Repo) -> LLMProviderResponse:
    """Retrieve a single LLM provider by ID (API key stripped)."""
    provider = await repo.get_provider(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")
    return _to_response(provider)


@router.put("/{provider_id}", dependencies=[AdminGuard])
async def update_provider(
    provider_id: str, provider: LLMProvider, repo: Repo
) -> LLMProviderResponse:
    """Update an existing LLM provider."""
    existing = await repo.get_provider(provider_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")
    await repo.update_provider(provider)
    # Re-fetch to get updated timestamps
    updated = await repo.get_provider(provider_id)
    return _to_response(updated or provider)


@router.delete("/{provider_id}", status_code=204, dependencies=[AdminGuard])
async def delete_provider(provider_id: str, repo: Repo) -> Response:
    """Remove an LLM provider."""
    existing = await repo.get_provider(provider_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")
    await repo.delete_provider(provider_id)
    return Response(status_code=204)


@router.post("/{provider_id}/test", dependencies=[AdminGuard])
async def test_provider(provider_id: str, repo: Repo) -> ProviderHealthStatus:
    """Test connectivity to an LLM provider."""
    provider = await repo.get_provider(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")
    checker = LLMHealthChecker()
    return await checker.check(provider)


@router.put("/{provider_id}/default", dependencies=[AdminGuard])
async def set_default_provider(provider_id: str, repo: Repo) -> LLMProviderResponse:
    """Set an LLM provider as the default."""
    provider = await repo.get_provider(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")
    await repo.set_default(provider_id)
    # Re-fetch to get updated state
    updated = await repo.get_provider(provider_id)
    return _to_response(updated or provider)
