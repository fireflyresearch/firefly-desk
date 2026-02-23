# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Settings REST API -- user preferences and app-wide configuration."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from flydesk.rbac.guards import AdminSettings
from flydesk.settings.models import AgentSettings, UserSettings
from flydesk.settings.repository import SettingsRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_settings_repo() -> SettingsRepository:
    """Provide a SettingsRepository instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_settings_repo must be overridden via app.dependency_overrides"
    )


Repo = Annotated[SettingsRepository, Depends(get_settings_repo)]


# ---------------------------------------------------------------------------
# User Settings
# ---------------------------------------------------------------------------


@router.get("/user")
async def get_user_settings(request: Request, repo: Repo) -> UserSettings:
    """Return the current user's settings (defaults if none saved)."""
    user = getattr(request.state, "user_session", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return await repo.get_user_settings(user.user_id)


@router.put("/user")
async def update_user_settings(
    request: Request, settings: UserSettings, repo: Repo
) -> UserSettings:
    """Update the current user's settings."""
    user = getattr(request.state, "user_session", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    await repo.update_user_settings(user.user_id, settings)
    return settings


# ---------------------------------------------------------------------------
# App Settings (admin only)
# ---------------------------------------------------------------------------


@router.get("/app", dependencies=[AdminSettings])
async def get_app_settings(repo: Repo) -> dict[str, str]:
    """Return all application-wide settings."""
    return await repo.get_all_app_settings()


@router.put("/app", dependencies=[AdminSettings])
async def update_app_settings(
    settings: dict[str, str], repo: Repo
) -> dict[str, str]:
    """Update application-wide settings (key-value pairs)."""
    for key, value in settings.items():
        await repo.set_app_setting(key, value)
    return settings


# ---------------------------------------------------------------------------
# Agent Settings (admin only)
# ---------------------------------------------------------------------------


@router.get("/agent", dependencies=[AdminSettings])
async def get_agent_settings(repo: Repo) -> AgentSettings:
    """Return the current agent customization settings."""
    return await repo.get_agent_settings()


@router.put("/agent", dependencies=[AdminSettings])
async def update_agent_settings(
    settings: AgentSettings, request: Request, repo: Repo
) -> AgentSettings:
    """Update agent customization settings.

    Also invalidates the cached :class:`AgentProfile` on the live
    :class:`AgentCustomizationService` so the next turn picks up changes.
    """
    await repo.set_agent_settings(settings)

    # Invalidate the in-memory cache on the live customization service.
    customization_svc = getattr(
        getattr(request.app, "state", None), "customization_service", None
    )
    if customization_svc is not None:
        customization_svc.invalidate_cache()

    return settings


# ---------------------------------------------------------------------------
# Analysis Configuration (admin only)
# ---------------------------------------------------------------------------


class AnalysisConfig(BaseModel):
    """Analysis / auto-discovery toggle configuration."""

    auto_analyze: bool = False


@router.get("/analysis", dependencies=[AdminSettings])
async def get_analysis_config(request: Request, repo: Repo) -> AnalysisConfig:
    """Return the current analysis configuration (from DB, falling back to env)."""
    settings = await repo.get_all_app_settings(category="analysis")
    config = getattr(request.app.state, "config", None)

    auto_analyze_str = settings.get(
        "auto_analyze",
        str(config.auto_analyze).lower() if config else "false",
    )
    return AnalysisConfig(auto_analyze=auto_analyze_str in ("true", "1", "True"))


@router.put("/analysis", dependencies=[AdminSettings])
async def update_analysis_config(
    body: AnalysisConfig, repo: Repo
) -> AnalysisConfig:
    """Update analysis configuration (auto_analyze toggle)."""
    await repo.set_app_setting(
        "auto_analyze", str(body.auto_analyze).lower(), category="analysis"
    )
    return body


# ---------------------------------------------------------------------------
# Embedding Configuration (admin only)
# ---------------------------------------------------------------------------

_EMBEDDING_KEYS = {
    "embedding_model": "embedding",
    "embedding_api_key": "embedding",
    "embedding_base_url": "embedding",
    "embedding_dimensions": "embedding",
}


class EmbeddingConfig(BaseModel):
    """Embedding provider configuration."""

    embedding_model: str = "openai:text-embedding-3-small"
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_dimensions: int = 1536


class EmbeddingTestResult(BaseModel):
    """Result of an embedding test."""

    success: bool
    provider: str
    model: str
    dimensions: int
    sample_vector_length: int | None = None
    error: str | None = None


@router.get("/embedding", dependencies=[AdminSettings])
async def get_embedding_config(request: Request, repo: Repo) -> EmbeddingConfig:
    """Return current embedding configuration (from DB, falling back to env)."""
    settings = await repo.get_all_app_settings(category="embedding")
    config = getattr(request.app.state, "config", None)

    return EmbeddingConfig(
        embedding_model=settings.get(
            "embedding_model",
            config.embedding_model if config else "openai:text-embedding-3-small",
        ),
        embedding_api_key=_mask_key(
            settings.get(
                "embedding_api_key",
                config.embedding_api_key if config else "",
            )
        ),
        embedding_base_url=settings.get(
            "embedding_base_url",
            config.embedding_base_url if config else "",
        ),
        embedding_dimensions=int(
            settings.get(
                "embedding_dimensions",
                str(config.embedding_dimensions) if config else "1536",
            )
        ),
    )


@router.put("/embedding", dependencies=[AdminSettings])
async def update_embedding_config(
    body: EmbeddingConfig, request: Request, repo: Repo
) -> EmbeddingConfig:
    """Update embedding configuration and reinitialize the provider."""
    await repo.set_app_setting(
        "embedding_model", body.embedding_model, category="embedding"
    )
    # Only update API key if it's not the masked placeholder
    if body.embedding_api_key and not body.embedding_api_key.startswith("***"):
        await repo.set_app_setting(
            "embedding_api_key", body.embedding_api_key, category="embedding"
        )
    await repo.set_app_setting(
        "embedding_base_url", body.embedding_base_url, category="embedding"
    )
    await repo.set_app_setting(
        "embedding_dimensions", str(body.embedding_dimensions), category="embedding"
    )

    # Reinitialize the embedding provider with new settings
    await _reinitialize_embedding_provider(request.app, repo)

    return await get_embedding_config(request, repo)


@router.post("/embedding/test", dependencies=[AdminSettings])
async def test_embedding(request: Request, repo: Repo) -> EmbeddingTestResult:
    """Test the current embedding configuration by embedding a sample text."""
    settings = await repo.get_all_app_settings(category="embedding")
    config = getattr(request.app.state, "config", None)

    model_str = settings.get(
        "embedding_model",
        config.embedding_model if config else "openai:text-embedding-3-small",
    )
    api_key = settings.get(
        "embedding_api_key",
        config.embedding_api_key if config else "",
    )
    base_url = settings.get(
        "embedding_base_url",
        config.embedding_base_url if config else "",
    )
    dimensions = int(
        settings.get(
            "embedding_dimensions",
            str(config.embedding_dimensions) if config else "1536",
        )
    )

    parts = model_str.split(":", 1)
    if len(parts) != 2:
        return EmbeddingTestResult(
            success=False,
            provider="unknown",
            model=model_str,
            dimensions=dimensions,
            error=f"Invalid model format: {model_str!r}. Expected 'provider:model'.",
        )

    provider_name, model_name = parts

    try:
        from flydesk.knowledge.embeddings import LLMEmbeddingProvider
        from flydesk.llm.repository import LLMProviderRepository

        http_client = getattr(request.app.state, "http_client", None)
        session_factory = getattr(request.app.state, "session_factory", None)

        if not http_client or not session_factory:
            return EmbeddingTestResult(
                success=False,
                provider=provider_name,
                model=model_name,
                dimensions=dimensions,
                error="Server not fully initialized.",
            )

        encryption_key = config.credential_encryption_key if config else ""
        llm_repo = LLMProviderRepository(session_factory, encryption_key)

        test_provider = LLMEmbeddingProvider(
            http_client=http_client,
            embedding_model=model_str,
            dimensions=dimensions,
            llm_repo=llm_repo,
            api_key=api_key or None,
            base_url=base_url or None,
        )

        vectors = await test_provider.embed(["Hello, this is a test embedding."])
        vec = vectors[0]

        is_zero = all(v == 0.0 for v in vec)
        if is_zero:
            return EmbeddingTestResult(
                success=False,
                provider=provider_name,
                model=model_name,
                dimensions=dimensions,
                error="Received zero vector — no API key or provider unreachable.",
            )

        return EmbeddingTestResult(
            success=True,
            provider=provider_name,
            model=model_name,
            dimensions=dimensions,
            sample_vector_length=len(vec),
        )

    except Exception as exc:
        logger.error("Embedding test failed: %s", exc, exc_info=True)
        return EmbeddingTestResult(
            success=False,
            provider=provider_name,
            model=model_name,
            dimensions=dimensions,
            error=str(exc),
        )


async def _reinitialize_embedding_provider(app: object, repo: SettingsRepository) -> None:
    """Reinitialize the live embedding provider from updated DB settings."""
    try:
        from flydesk.knowledge.embeddings import LLMEmbeddingProvider

        settings = await repo.get_all_app_settings(category="embedding")
        config = getattr(app, "state", None)
        if config is None:
            return
        app_config = getattr(config, "config", None)

        model_str = settings.get(
            "embedding_model",
            app_config.embedding_model if app_config else "openai:text-embedding-3-small",
        )
        api_key = settings.get(
            "embedding_api_key",
            app_config.embedding_api_key if app_config else "",
        )
        base_url = settings.get(
            "embedding_base_url",
            app_config.embedding_base_url if app_config else "",
        )
        dimensions = int(
            settings.get(
                "embedding_dimensions",
                str(app_config.embedding_dimensions) if app_config else "1536",
            )
        )

        http_client = getattr(config, "http_client", None)
        session_factory = getattr(config, "session_factory", None)
        if not http_client or not session_factory:
            return

        encryption_key = app_config.credential_encryption_key if app_config else ""
        from flydesk.llm.repository import LLMProviderRepository

        llm_repo = LLMProviderRepository(session_factory, encryption_key)

        new_provider = LLMEmbeddingProvider(
            http_client=http_client,
            embedding_model=model_str,
            dimensions=dimensions,
            llm_repo=llm_repo,
            api_key=api_key or None,
            base_url=base_url or None,
        )

        # Hot-swap the provider in the indexer and retriever via desk_agent
        desk_agent = getattr(config, "desk_agent", None)
        if desk_agent and hasattr(desk_agent, "_context_enricher"):
            enricher = desk_agent._context_enricher
            if hasattr(enricher, "_retriever"):
                enricher._retriever._embedding_provider = new_provider

        logger.info("Embedding provider reinitialized: %s", model_str)

    except Exception:
        logger.warning("Failed to reinitialize embedding provider.", exc_info=True)


def _mask_key(key: str) -> str:
    """Mask an API key for display, showing only last 4 characters."""
    if not key or len(key) <= 8:
        return key
    return "***" + key[-4:]
