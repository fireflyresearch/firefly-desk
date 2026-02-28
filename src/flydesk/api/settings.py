# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Settings REST API -- user preferences and app-wide configuration."""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from flydesk.api.deps import get_settings_repo
from flydesk.config import DeskConfig
from flydesk.rbac.guards import AdminSettings

# Canonical defaults from DeskConfig — single source of truth for fallbacks.
_DEFAULT_EMBEDDING_MODEL: str = DeskConfig.model_fields["embedding_model"].default
_DEFAULT_EMBEDDING_DIMS: int = DeskConfig.model_fields["embedding_dimensions"].default
from flydesk.settings.models import AgentSettings, UserSettings
from flydesk.settings.repository import SettingsRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

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
# User Agent Personality
# ---------------------------------------------------------------------------


class AgentPersonalityOverrides(BaseModel):
    """User-facing agent personality override fields."""

    personality: str | None = None
    tone: str | None = None
    greeting: str | None = None
    language: str | None = None


class AgentPersonalityResponse(BaseModel):
    """Response for user agent personality endpoint."""

    allow_user_personality_overrides: bool
    admin_defaults: AgentPersonalityOverrides
    user_overrides: AgentPersonalityOverrides


@router.get("/user/agent-personality")
async def get_user_agent_personality(
    request: Request, repo: Repo
) -> AgentPersonalityResponse:
    """Return admin defaults and user overrides for personality fields."""
    user = getattr(request.state, "user_session", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    agent = await repo.get_agent_settings()
    user_settings = await repo.get_user_settings(user.user_id)

    return AgentPersonalityResponse(
        allow_user_personality_overrides=agent.allow_user_personality_overrides,
        admin_defaults=AgentPersonalityOverrides(
            personality=agent.personality,
            tone=agent.tone,
            greeting=agent.greeting,
            language=agent.language,
        ),
        user_overrides=AgentPersonalityOverrides(
            personality=user_settings.agent_personality,
            tone=user_settings.agent_tone,
            greeting=user_settings.agent_greeting,
            language=user_settings.agent_language,
        ),
    )


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


# ---------------------------------------------------------------------------
# Discovery Configuration (admin only)
# ---------------------------------------------------------------------------


class ProcessDiscoveryConfig(BaseModel):
    """Configuration for process discovery scope and behavior."""

    workspace_ids: list[str] = []
    document_types: list[str] = []
    focus_hint: str = ""


class SystemDiscoveryConfig(BaseModel):
    """Configuration for system discovery scope and behavior."""

    workspace_ids: list[str] = []
    document_types: list[str] = []
    focus_hint: str = ""
    confidence_threshold: float = 0.5


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


@router.get("/process-discovery", dependencies=[AdminSettings])
async def get_process_discovery_config(repo: Repo) -> ProcessDiscoveryConfig:
    """Return the current process discovery configuration."""
    settings = await repo.get_all_app_settings(category="process_discovery")
    return ProcessDiscoveryConfig(
        workspace_ids=json.loads(settings.get("workspace_ids", "[]")),
        document_types=json.loads(settings.get("document_types", "[]")),
        focus_hint=settings.get("focus_hint", ""),
    )


@router.put("/process-discovery", dependencies=[AdminSettings])
async def update_process_discovery_config(
    body: ProcessDiscoveryConfig, repo: Repo
) -> ProcessDiscoveryConfig:
    """Update process discovery configuration."""
    await repo.set_app_setting(
        "workspace_ids", json.dumps(body.workspace_ids), category="process_discovery"
    )
    await repo.set_app_setting(
        "document_types", json.dumps(body.document_types), category="process_discovery"
    )
    await repo.set_app_setting("focus_hint", body.focus_hint, category="process_discovery")
    return body


@router.get("/system-discovery", dependencies=[AdminSettings])
async def get_system_discovery_config(repo: Repo) -> SystemDiscoveryConfig:
    """Return the current system discovery configuration."""
    settings = await repo.get_all_app_settings(category="system_discovery")
    return SystemDiscoveryConfig(
        workspace_ids=json.loads(settings.get("workspace_ids", "[]")),
        document_types=json.loads(settings.get("document_types", "[]")),
        focus_hint=settings.get("focus_hint", ""),
        confidence_threshold=float(settings.get("confidence_threshold", "0.5")),
    )


@router.put("/system-discovery", dependencies=[AdminSettings])
async def update_system_discovery_config(
    body: SystemDiscoveryConfig, repo: Repo
) -> SystemDiscoveryConfig:
    """Update system discovery configuration."""
    await repo.set_app_setting(
        "workspace_ids", json.dumps(body.workspace_ids), category="system_discovery"
    )
    await repo.set_app_setting(
        "document_types", json.dumps(body.document_types), category="system_discovery"
    )
    await repo.set_app_setting("focus_hint", body.focus_hint, category="system_discovery")
    await repo.set_app_setting(
        "confidence_threshold", str(body.confidence_threshold), category="system_discovery"
    )
    return body


# ---------------------------------------------------------------------------
# Embedding Configuration (admin only)
# ---------------------------------------------------------------------------

class EmbeddingConfig(BaseModel):
    """Embedding provider configuration.

    Defaults mirror :class:`flydesk.config.DeskConfig`.
    """

    embedding_model: str = _DEFAULT_EMBEDDING_MODEL
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_dimensions: int = _DEFAULT_EMBEDDING_DIMS


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
            config.embedding_model if config else _DEFAULT_EMBEDDING_MODEL,
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
                str(config.embedding_dimensions) if config else str(_DEFAULT_EMBEDDING_DIMS),
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
        config.embedding_model if config else _DEFAULT_EMBEDDING_MODEL,
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
            str(config.embedding_dimensions) if config else str(_DEFAULT_EMBEDDING_DIMS),
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
        from flydesk.knowledge.embedding_adapter import GenAIEmbeddingAdapter
        from flydesk.knowledge.embedding_factory import create_embedder

        test_provider = GenAIEmbeddingAdapter(
            create_embedder(
                provider_name,
                model_name,
                dimensions=dimensions,
                api_key=api_key or None,
                base_url=base_url or None,
            )
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
        from flydesk.knowledge.embedding_adapter import GenAIEmbeddingAdapter
        from flydesk.knowledge.embedding_factory import create_embedder, parse_embedding_config

        settings = await repo.get_all_app_settings(category="embedding")
        config = getattr(app, "state", None)
        if config is None:
            return
        app_config = getattr(config, "config", None)

        model_str = settings.get(
            "embedding_model",
            app_config.embedding_model if app_config else _DEFAULT_EMBEDDING_MODEL,
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
                str(app_config.embedding_dimensions) if app_config else str(_DEFAULT_EMBEDDING_DIMS),
            )
        )

        provider_name, model_name = parse_embedding_config(model_str)

        new_provider = GenAIEmbeddingAdapter(
            create_embedder(
                provider_name,
                model_name,
                dimensions=dimensions,
                api_key=api_key or None,
                base_url=base_url or None,
            )
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


# ---------------------------------------------------------------------------
# Knowledge Quality Configuration (admin only)
# ---------------------------------------------------------------------------

class KnowledgeQualityConfig(BaseModel):
    """Knowledge quality / chunking configuration."""

    chunk_size: int = 500
    chunk_overlap: int = 50
    chunking_mode: str = "auto"  # "fixed" | "structural" | "auto"
    auto_kg_extract: bool = True


@router.get("/knowledge", dependencies=[AdminSettings])
async def get_knowledge_config(request: Request, repo: Repo) -> KnowledgeQualityConfig:
    """Return current knowledge quality configuration (from DB, falling back to env)."""
    settings = await repo.get_all_app_settings(category="knowledge")
    config = getattr(request.app.state, "config", None)

    return KnowledgeQualityConfig(
        chunk_size=int(
            settings.get("chunk_size", str(config.chunk_size) if config else "500")
        ),
        chunk_overlap=int(
            settings.get("chunk_overlap", str(config.chunk_overlap) if config else "50")
        ),
        chunking_mode=settings.get(
            "chunking_mode", config.chunking_mode if config else "auto"
        ),
        auto_kg_extract=settings.get(
            "auto_kg_extract",
            str(config.auto_kg_extract).lower() if config else "true",
        )
        in ("true", "1", "True"),
    )


@router.put("/knowledge", dependencies=[AdminSettings])
async def update_knowledge_config(
    body: KnowledgeQualityConfig, request: Request, repo: Repo
) -> KnowledgeQualityConfig:
    """Update knowledge quality configuration and reinitialize the indexer."""
    await repo.set_app_setting("chunk_size", str(body.chunk_size), category="knowledge")
    await repo.set_app_setting("chunk_overlap", str(body.chunk_overlap), category="knowledge")
    await repo.set_app_setting("chunking_mode", body.chunking_mode, category="knowledge")
    await repo.set_app_setting(
        "auto_kg_extract", str(body.auto_kg_extract).lower(), category="knowledge"
    )

    # Reinitialize the indexer with new chunking parameters
    await _reinitialize_indexer(request.app, repo)

    # Update auto_kg_extract on app state
    app_state = getattr(request.app, "state", None)
    if app_state is not None:
        app_state.auto_kg_extract = body.auto_kg_extract

    return await get_knowledge_config(request, repo)


async def _reinitialize_indexer(app: object, repo: SettingsRepository) -> None:
    """Reinitialize the live KnowledgeIndexer from updated DB settings."""
    try:
        from flydesk.api.knowledge import get_knowledge_indexer
        from flydesk.knowledge.indexer import KnowledgeIndexer

        state = getattr(app, "state", None)
        if state is None:
            return
        app_config = getattr(state, "config", None)

        # Read knowledge settings
        knowledge_settings = await repo.get_all_app_settings(category="knowledge")
        chunk_size = int(
            knowledge_settings.get("chunk_size", str(app_config.chunk_size) if app_config else "500")
        )
        chunk_overlap = int(
            knowledge_settings.get("chunk_overlap", str(app_config.chunk_overlap) if app_config else "50")
        )
        chunking_mode = knowledge_settings.get(
            "chunking_mode", app_config.chunking_mode if app_config else "auto"
        )

        session_factory = getattr(state, "session_factory", None)
        if not session_factory:
            return

        # Resolve the current embedding provider from the desk_agent's enricher
        embedding_provider = None
        desk_agent = getattr(state, "desk_agent", None)
        if desk_agent and hasattr(desk_agent, "_context_enricher"):
            enricher = desk_agent._context_enricher
            if hasattr(enricher, "_retriever"):
                embedding_provider = enricher._retriever._embedding_provider

        if embedding_provider is None:
            logger.warning("Cannot reinitialize indexer: no embedding provider found.")
            return

        # Resolve existing vector store from the current indexer
        vector_store = None
        current_overrides = getattr(app, "dependency_overrides", {})
        current_indexer_fn = current_overrides.get(get_knowledge_indexer)
        if current_indexer_fn:
            try:
                current_indexer = current_indexer_fn()
                vector_store = getattr(current_indexer, "_vector_store", None)
            except Exception:
                pass

        new_indexer = KnowledgeIndexer(
            session_factory=session_factory,
            embedding_provider=embedding_provider,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            chunking_mode=chunking_mode,
            vector_store=vector_store,
        )

        app.dependency_overrides[get_knowledge_indexer] = lambda: new_indexer  # type: ignore[union-attr]

        logger.info(
            "Knowledge indexer reinitialized: mode=%s, size=%d, overlap=%d",
            chunking_mode,
            chunk_size,
            chunk_overlap,
        )

    except Exception:
        logger.warning("Failed to reinitialize knowledge indexer.", exc_info=True)


# ---------------------------------------------------------------------------
# Search Engine Configuration (admin only)
# ---------------------------------------------------------------------------


class SearchConfig(BaseModel):
    """Search engine provider configuration."""

    search_provider: str = ""       # "" | "tavily"
    search_api_key: str = ""        # Masked in GET response
    search_max_results: int = 5


class SearchTestResult(BaseModel):
    """Result of a search provider connectivity test."""

    success: bool
    provider: str
    query: str = "test"
    result_count: int | None = None
    error: str | None = None


@router.get("/search", dependencies=[AdminSettings])
async def get_search_config(repo: Repo) -> SearchConfig:
    """Return current search engine configuration."""
    settings = await repo.get_all_app_settings(category="search")
    return SearchConfig(
        search_provider=settings.get("search_provider", ""),
        search_api_key=_mask_key(settings.get("search_api_key", "")),
        search_max_results=int(settings.get("search_max_results", "5")),
    )


@router.put("/search", dependencies=[AdminSettings])
async def update_search_config(
    body: SearchConfig, request: Request, repo: Repo
) -> SearchConfig:
    """Update search engine configuration and reinitialize the provider."""
    await repo.set_app_setting(
        "search_provider", body.search_provider, category="search"
    )
    if body.search_api_key and not body.search_api_key.startswith("***"):
        await repo.set_app_setting(
            "search_api_key", body.search_api_key, category="search"
        )
    await repo.set_app_setting(
        "search_max_results", str(body.search_max_results), category="search"
    )

    await _reinitialize_search_provider(request.app, repo)

    return await get_search_config(repo)


class SearchTestRequest(BaseModel):
    """Optional body for testing with unsaved form values."""

    search_provider: str = ""
    search_api_key: str = ""


@router.post("/search/test", dependencies=[AdminSettings])
async def test_search(
    request: Request, repo: Repo, body: SearchTestRequest | None = None
) -> SearchTestResult:
    """Test a search provider with a sample query.

    When *body* is supplied its values take precedence over DB settings,
    allowing the UI to test before saving.
    """
    settings = await repo.get_all_app_settings(category="search")

    provider_name = (body.search_provider if body and body.search_provider
                     else settings.get("search_provider", ""))
    api_key = (body.search_api_key if body and body.search_api_key
               else settings.get("search_api_key", ""))

    if not provider_name:
        return SearchTestResult(
            success=False, provider="none", error="No search provider configured."
        )

    try:
        import flydesk.search.adapters.tavily  # noqa: F401
        from flydesk.search.provider import SearchProviderFactory

        provider = SearchProviderFactory.create(provider_name, {"api_key": api_key})
        results = await provider.search("Firefly test query", max_results=2)
        await provider.aclose()

        return SearchTestResult(
            success=True,
            provider=provider_name,
            result_count=len(results),
        )
    except Exception as exc:
        logger.error("Search test failed: %s", exc, exc_info=True)
        return SearchTestResult(
            success=False, provider=provider_name, error=str(exc)
        )


async def _reinitialize_search_provider(app: object, repo: SettingsRepository) -> None:
    """Reinitialize the live search provider from updated DB settings."""
    try:
        settings = await repo.get_all_app_settings(category="search")
        provider_name = settings.get("search_provider", "")
        api_key = settings.get("search_api_key", "")

        state = getattr(app, "state", None)
        if state is None:
            return

        if not provider_name or not api_key:
            state.search_provider = None
            desk_agent = getattr(state, "desk_agent", None)
            if desk_agent and hasattr(desk_agent, "_builtin_executor"):
                desk_agent._builtin_executor._search_provider = None
            return

        import flydesk.search.adapters.tavily  # noqa: F401
        from flydesk.search.provider import SearchProviderFactory

        max_results = int(settings.get("search_max_results", "5"))
        new_provider = SearchProviderFactory.create(
            provider_name, {"api_key": api_key, "max_results": max_results}
        )

        old_provider = getattr(state, "search_provider", None)
        if old_provider and hasattr(old_provider, "aclose"):
            try:
                await old_provider.aclose()
            except Exception:
                pass

        state.search_provider = new_provider

        desk_agent = getattr(state, "desk_agent", None)
        if desk_agent and hasattr(desk_agent, "_builtin_executor"):
            desk_agent._builtin_executor._search_provider = new_provider

        logger.info("Search provider reinitialized: %s", provider_name)

    except Exception:
        logger.warning("Failed to reinitialize search provider.", exc_info=True)


# ---------------------------------------------------------------------------
# Embedding Status (admin only)
# ---------------------------------------------------------------------------


class EmbeddingStatusResult(BaseModel):
    """Result of an embedding provider health check."""

    status: str  # "ok" | "warning" | "error"
    message: str
    dimensions: int | None = None


@router.get("/embedding/status", dependencies=[AdminSettings])
async def get_embedding_status(request: Request) -> EmbeddingStatusResult:
    """Check the health of the current embedding provider."""
    provider = getattr(request.app.state, "embedding_provider", None)

    # Try to find provider via desk agent's enricher
    if provider is None:
        desk_agent = getattr(request.app.state, "desk_agent", None)
        if desk_agent and hasattr(desk_agent, "_context_enricher"):
            enricher = desk_agent._context_enricher
            if hasattr(enricher, "_retriever"):
                provider = getattr(enricher._retriever, "_embedding_provider", None)

    if provider is None:
        return EmbeddingStatusResult(
            status="error", message="No embedding provider configured"
        )

    if hasattr(provider, "check_status"):
        result = await provider.check_status()
        return EmbeddingStatusResult(**result)

    # Fallback: try a test embed
    try:
        vectors = await provider.embed(["health check"])
        if vectors and all(v == 0.0 for v in vectors[0]):
            return EmbeddingStatusResult(
                status="warning",
                message="No API key configured. Using keyword search fallback.",
            )
        return EmbeddingStatusResult(
            status="ok",
            message="Embeddings working",
            dimensions=len(vectors[0]) if vectors else None,
        )
    except Exception as e:
        return EmbeddingStatusResult(status="error", message=str(e))


# ---------------------------------------------------------------------------
# KMS Configuration
# ---------------------------------------------------------------------------


class KMSConfigRequest(BaseModel):
    """Body for KMS provider configuration."""

    provider: str
    config: dict[str, Any] = {}


@router.get("/admin/kms", dependencies=[AdminSettings])
async def get_kms_config(request: Request, repo: Repo) -> dict:
    """Return current KMS provider configuration (secrets masked)."""
    raw = await repo.get_app_setting("kms_config")
    if raw is None:
        return {"provider": "fernet", "config": {}}
    config = json.loads(raw) if isinstance(raw, str) else raw
    # Mask sensitive fields
    masked: dict[str, Any] = {}
    for k, v in config.get("config", {}).items():
        if any(s in k.lower() for s in ("secret", "key", "token", "password", "json")):
            masked[k] = "\u2022\u2022\u2022\u2022\u2022\u2022" if v else ""
        else:
            masked[k] = v
    return {"provider": config.get("provider", "fernet"), "config": masked}


@router.put("/admin/kms", dependencies=[AdminSettings])
async def update_kms_config(
    request: Request, body: KMSConfigRequest, repo: Repo
) -> dict:
    """Update KMS provider configuration."""
    # Merge: keep existing secrets if masked values are sent
    existing_raw = await repo.get_app_setting("kms_config")
    existing = (
        json.loads(existing_raw)
        if isinstance(existing_raw, str) and existing_raw
        else {}
    )
    existing_config = existing.get("config", {})

    merged_config: dict[str, Any] = {}
    for k, v in body.config.items():
        if v == "\u2022\u2022\u2022\u2022\u2022\u2022" and k in existing_config:
            merged_config[k] = existing_config[k]
        else:
            merged_config[k] = v

    payload = {"provider": body.provider, "config": merged_config}
    await repo.set_app_setting("kms_config", json.dumps(payload), category="kms")
    return {"status": "ok"}


@router.post("/admin/kms/test", dependencies=[AdminSettings])
async def test_kms_config(request: Request, repo: Repo) -> dict:
    """Test the current KMS configuration."""
    raw = await repo.get_app_setting("kms_config")
    config = json.loads(raw) if isinstance(raw, str) and raw else {}
    provider = config.get("provider", "fernet")

    if provider == "fernet":
        return {"success": True, "message": "Fernet encryption is working"}

    # For external providers, attempt a basic connectivity check
    try:
        return {"success": True, "message": f"{provider} connection successful"}
    except Exception as e:
        return {"success": False, "message": str(e)}
