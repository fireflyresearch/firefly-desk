# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Public LLM status endpoint for the chat UI.

Returns the active model name and connection health without requiring
admin privileges. Also exposes the fallback model configuration for
both display and admin editing.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from flydesk.llm.health import LLMHealthChecker
from flydesk.llm.repository import LLMProviderRepository
from flydesk.rbac.guards import AdminLLM

_logger = logging.getLogger(__name__)

router = APIRouter(tags=["llm-status"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_llm_repo() -> LLMProviderRepository:
    raise NotImplementedError("get_llm_repo must be overridden via app.dependency_overrides")


Repo = Annotated[LLMProviderRepository, Depends(get_llm_repo)]


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class LLMStatus(BaseModel):
    """Public-facing LLM status for the chat UI."""

    provider_name: str | None = None
    provider_type: str | None = None
    model: str | None = None
    status: str = "unknown"  # "connected" | "degraded" | "disconnected" | "unknown"
    latency_ms: float | None = None
    fallback_models: list[str] = []


class FallbackConfig(BaseModel):
    """Admin-editable fallback model configuration."""

    provider_type: str
    fallback_models: list[str]


class UpdateFallbackRequest(BaseModel):
    """Body for PUT /api/admin/llm/fallback."""

    fallback_models: dict[str, list[str]]


# ---------------------------------------------------------------------------
# Public endpoint -- any authenticated user
# ---------------------------------------------------------------------------


@router.get("/api/llm/status")
async def get_llm_status(request: Request, repo: Repo) -> LLMStatus:
    """Return the active LLM provider, model, and health for the chat UI."""
    user_session = getattr(request.state, "user_session", None)
    if user_session is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        provider = await repo.get_default_provider()
    except Exception:
        _logger.debug("Failed to fetch default LLM provider.", exc_info=True)
        return LLMStatus(status="disconnected")

    if provider is None:
        return LLMStatus(status="disconnected")

    # Get fallback models
    from flydesk.agent.genai_bridge import _PROVIDER_FALLBACK_MODELS

    pt = provider.provider_type.value if hasattr(provider.provider_type, "value") else str(provider.provider_type)
    fallbacks = _PROVIDER_FALLBACK_MODELS.get(pt, [])

    # Quick health check
    status = "connected"
    latency_ms = None
    try:
        checker = LLMHealthChecker()
        health = await checker.check(provider)
        if health.reachable:
            status = "connected"
            latency_ms = health.latency_ms
        else:
            status = "degraded"
    except Exception:
        status = "degraded"

    return LLMStatus(
        provider_name=provider.name,
        provider_type=pt,
        model=provider.default_model,
        status=status,
        latency_ms=latency_ms,
        fallback_models=fallbacks,
    )


# ---------------------------------------------------------------------------
# Admin endpoints -- fallback model configuration
# ---------------------------------------------------------------------------


@router.get("/api/admin/llm/fallback", dependencies=[AdminLLM])
async def get_fallback_config() -> dict[str, list[str]]:
    """Return the current fallback model configuration per provider type."""
    from flydesk.agent.genai_bridge import _PROVIDER_FALLBACK_MODELS

    return dict(_PROVIDER_FALLBACK_MODELS)


@router.put("/api/admin/llm/fallback", dependencies=[AdminLLM])
async def update_fallback_config(body: UpdateFallbackRequest) -> dict[str, list[str]]:
    """Update fallback models per provider type (runtime-only, not persisted to DB yet)."""
    from flydesk.agent.genai_bridge import _PROVIDER_FALLBACK_MODELS

    for provider_type, models in body.fallback_models.items():
        _PROVIDER_FALLBACK_MODELS[provider_type] = models

    return dict(_PROVIDER_FALLBACK_MODELS)
