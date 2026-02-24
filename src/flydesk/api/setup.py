# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Setup / installation wizard API.

Provides status information about the current deployment and, in dev mode,
allows seeding and configuring the instance from the web UI.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from flydesk.api.events import SSEEvent, SSEEventType

router = APIRouter(prefix="/api/setup", tags=["setup"])

logger = logging.getLogger(__name__)


class SetupStatus(BaseModel):
    """Current deployment status returned by the setup endpoint."""

    dev_mode: bool
    database_configured: bool
    oidc_configured: bool
    has_seed_data: bool
    setup_completed: bool
    llm_configured: bool
    has_admin_user: bool
    has_sso_configured: bool
    fqdn: str
    locale_language: str
    app_title: str
    app_version: str
    agent_name: str
    accent_color: str
    agent_avatar_url: str = ""
    agent_display_name: str = ""


class CreateAdminRequest(BaseModel):
    """Request body for creating the initial admin user during setup."""

    username: str
    email: str
    display_name: str
    password: str


class SetupSSORequest(BaseModel):
    """Request body for configuring an SSO/OIDC provider during setup."""

    provider_type: str
    display_name: str
    issuer_url: str
    client_id: str
    client_secret: str | None = None
    tenant_id: str | None = None
    scopes: list[str] | None = None
    allowed_email_domains: list[str] | None = None


class TestSSORequest(BaseModel):
    """Request body for testing SSO issuer connectivity."""

    issuer_url: str


class SetupFQDNRequest(BaseModel):
    """Request body for configuring the FQDN during setup."""

    fqdn: str  # e.g., "myapp.example.com" or "localhost:5173"
    protocol: str = "https"  # "http" for dev


class SetupLocaleRequest(BaseModel):
    """Request body for configuring locale during setup."""

    language: str  # e.g., "en-US"
    timezone: str  # e.g., "America/New_York"
    country: str = ""  # e.g., "US" (ISO 3166-1 alpha-2)


class SeedRequest(BaseModel):
    """Request body for seeding or removing seed data."""

    domain: str = "banking"
    remove: bool = False
    include_systems: bool = True
    include_knowledge: bool = True
    include_skills: bool = True
    include_kg: bool = True
    include_discovery: bool = True


class SeedResult(BaseModel):
    """Result of a seed operation."""

    success: bool
    message: str


class LLMProviderConfig(BaseModel):
    """LLM provider configuration from the setup wizard."""

    name: str
    provider_type: str
    api_key: str | None = None
    base_url: str | None = None
    model_id: str | None = None
    model_name: str | None = None


class AgentSettingsConfig(BaseModel):
    """Agent customization from the setup wizard."""

    name: str = "Ember"
    display_name: str = "Ember"
    personality: str = "warm, professional, knowledgeable"
    tone: str = "friendly"
    greeting: str = "Hello! I'm {name}, your intelligent assistant."


class EmbeddingSetupConfig(BaseModel):
    """Embedding provider configuration from the setup wizard."""

    provider: str  # "openai", "voyage", "google", "ollama"
    model: str
    api_key: str | None = None
    base_url: str | None = None
    dimensions: int = 1536


class VectorStoreSetupConfig(BaseModel):
    """Vector store configuration from the setup wizard."""

    type: str  # "sqlite", "pgvector", "chromadb", "pinecone"
    chroma_path: str | None = None
    chroma_url: str | None = None
    pinecone_api_key: str | None = None
    pinecone_index_name: str | None = None
    pinecone_environment: str | None = None


class ConfigureRequest(BaseModel):
    """Request body for the setup wizard configure endpoint."""

    llm_provider: LLMProviderConfig | None = None
    embedding: EmbeddingSetupConfig | None = None
    vector_store: VectorStoreSetupConfig | None = None
    seed_data: bool | None = None
    agent_settings: AgentSettingsConfig | None = None


class ConfigureResult(BaseModel):
    """Result of a configure operation."""

    success: bool
    message: str
    details: dict | None = None


class LLMTestRequest(BaseModel):
    """Request body for testing an LLM provider's connectivity."""

    provider_type: str
    api_key: str | None = None
    base_url: str | None = None


class LLMTestResult(BaseModel):
    """Result of an LLM connectivity test."""

    reachable: bool
    latency_ms: float | None = None
    error: str | None = None


class TestEmbeddingRequest(BaseModel):
    """Request body for testing an embedding provider."""

    provider: str  # "openai", "voyage", "google", "ollama"
    api_key: str = ""
    base_url: str = ""
    model: str
    dimensions: int = 0


class TestEmbeddingResult(BaseModel):
    """Result of an embedding test."""

    success: bool
    dimensions: int = 0
    duration_ms: float = 0
    error: str | None = None


class DatabaseTestRequest(BaseModel):
    """Request body for testing database connectivity."""

    connection_string: str = ""


class DatabaseTestResult(BaseModel):
    """Result of a database connectivity test."""

    success: bool
    database_type: str = ""
    error: str | None = None


class WizardState(BaseModel):
    """Current wizard state for resumption."""

    step: str
    completed: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _friendly_error(exc: Exception, context: str) -> str:
    """Map common exception types to user-friendly error messages.

    Returns a human-readable string with actionable guidance instead of
    raw Python tracebacks or cryptic library messages.
    """
    msg = str(exc)
    if "Connection refused" in msg or "ConnectError" in msg:
        return (
            f"Could not connect to the {context} server. "
            "Please check the URL and ensure the service is running."
        )
    if "401" in msg or "Unauthorized" in msg or "invalid_api_key" in msg:
        return f"Authentication failed. Please check your {context} API key."
    if "403" in msg or "Forbidden" in msg:
        return (
            f"Access denied. Your API key may not have the required "
            f"permissions for {context}."
        )
    if "404" in msg:
        return f"The {context} endpoint was not found. Please check the URL."
    if "timeout" in msg.lower() or "Timeout" in msg:
        return (
            f"Connection to {context} timed out. "
            "Please check the URL and try again."
        )
    if "SSL" in msg or "certificate" in msg.lower():
        return (
            f"SSL/TLS error connecting to {context}. "
            "Check certificate configuration."
        )
    if "Name or service not known" in msg or "getaddrinfo" in msg:
        return (
            f"Could not resolve the {context} hostname. "
            "Please check the URL."
        )
    # Fall back to original message, cleaned up
    return f"{context} error: {msg.split(chr(10))[0][:200]}"


@router.post("/test-llm")
async def test_llm_provider(body: LLMTestRequest) -> LLMTestResult:
    """Test LLM provider connectivity without auth or persistence.

    This is used by the setup wizard to verify provider credentials
    before the user has any permissions or stored configuration.
    """
    from flydesk.llm.health import LLMHealthChecker
    from flydesk.llm.models import LLMProvider, ProviderType

    try:
        provider_type = ProviderType(body.provider_type)
    except ValueError:
        return LLMTestResult(
            reachable=False,
            error=f"Unknown provider type: {body.provider_type}",
        )

    # Create a transient provider (not persisted) just for the health check.
    transient = LLMProvider(
        id="__setup_test__",
        name="Setup Test",
        provider_type=provider_type,
        api_key=body.api_key,
        base_url=body.base_url,
    )

    checker = LLMHealthChecker()
    status = await checker.check(transient)

    error = status.error
    if error:
        # Wrap the raw health-checker error in a user-friendly message.
        error = _friendly_error(Exception(error), "LLM provider")

    return LLMTestResult(
        reachable=status.reachable,
        latency_ms=status.latency_ms,
        error=error,
    )


@router.post("/test-embedding")
async def test_embedding(body: TestEmbeddingRequest) -> TestEmbeddingResult:
    """Generate a test embedding to verify provider configuration.

    This is used by the setup wizard to verify embedding credentials
    before the user has any permissions or stored configuration.
    No authentication is required.
    """
    import httpx

    model_str = f"{body.provider}:{body.model}"
    dimensions = body.dimensions or 1536

    try:
        from flydesk.knowledge.embeddings import LLMEmbeddingProvider

        async with httpx.AsyncClient(timeout=30.0) as http_client:
            provider = LLMEmbeddingProvider(
                http_client=http_client,
                embedding_model=model_str,
                dimensions=dimensions,
                llm_repo=None,  # type: ignore[arg-type]
                api_key=body.api_key or None,
                base_url=body.base_url or None,
            )

            start = time.monotonic()
            vectors = await provider.embed(["Hello, world!"])
            elapsed_ms = (time.monotonic() - start) * 1000

            vec = vectors[0]
            if all(v == 0.0 for v in vec):
                return TestEmbeddingResult(
                    success=False,
                    dimensions=0,
                    duration_ms=elapsed_ms,
                    error=(
                        "Embedding returned empty results. This usually means "
                        "the API key is missing or invalid for the selected provider."
                    ),
                )

            return TestEmbeddingResult(
                success=True,
                dimensions=len(vec),
                duration_ms=round(elapsed_ms, 1),
            )
    except Exception as exc:
        logger.error("Embedding test failed: %s", exc, exc_info=True)
        return TestEmbeddingResult(
            success=False,
            error=_friendly_error(exc, "embedding provider"),
        )


@router.post("/test-database")
async def test_database(body: DatabaseTestRequest, request: Request) -> DatabaseTestResult:
    """Test database connectivity.

    If no connection_string is provided, test the current database connection
    (which should always succeed since the application is already running).
    If a connection_string is provided, attempt to connect and execute a
    simple query to verify connectivity.
    """
    from sqlalchemy import text

    if not body.connection_string:
        # Test the current database -- just verify the session factory works.
        session_factory = getattr(request.app.state, "session_factory", None)
        if not session_factory:
            return DatabaseTestResult(
                success=False,
                database_type="unknown",
                error="No database session available.",
            )
        try:
            async with session_factory() as session:
                await session.execute(text("SELECT 1"))
            from flydesk.config import get_config

            config = get_config()
            db_type = "PostgreSQL" if "postgresql" in config.database_url else "SQLite"
            return DatabaseTestResult(success=True, database_type=db_type)
        except Exception as exc:
            logger.error("Current database test failed: %s", exc)
            return DatabaseTestResult(
                success=False,
                database_type="unknown",
                error=_friendly_error(exc, "database"),
            )
    else:
        # Test the provided connection string.
        from sqlalchemy.engine import make_url
        from sqlalchemy.ext.asyncio import create_async_engine

        _ALLOWED_SCHEMES = {"postgresql+asyncpg", "sqlite+aiosqlite"}

        try:
            url = make_url(body.connection_string)
        except Exception:
            return DatabaseTestResult(
                success=False,
                database_type="unknown",
                error="Invalid connection string format.",
            )

        if url.drivername not in _ALLOWED_SCHEMES:
            return DatabaseTestResult(
                success=False,
                database_type="unknown",
                error=f"Unsupported database scheme: {url.drivername}. "
                f"Allowed: {', '.join(sorted(_ALLOWED_SCHEMES))}",
            )

        db_type = "PostgreSQL" if "postgresql" in url.drivername else "SQLite"
        engine = None
        try:
            engine = create_async_engine(url)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return DatabaseTestResult(success=True, database_type=db_type)
        except Exception as exc:
            logger.error("Database connection test failed: %s", exc)
            return DatabaseTestResult(
                success=False,
                database_type=db_type,
                error=_friendly_error(exc, "database"),
            )
        finally:
            if engine:
                await engine.dispose()


@router.get("/status")
async def get_setup_status(request: Request) -> SetupStatus:
    """Return the current deployment configuration status."""
    from flydesk import __version__
    from flydesk.config import get_config

    config = get_config()

    # Check if there's any seed data by looking for systems
    has_seed = False
    setup_completed = False
    llm_configured = False
    has_admin_user = False
    has_sso_configured = False
    fqdn = ""
    locale_language = ""
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory:
        from flydesk.catalog.repository import CatalogRepository

        repo = CatalogRepository(session_factory)
        systems = await repo.list_systems()
        has_seed = len(systems) > 0

        # Check whether initial setup has been completed
        from flydesk.settings.repository import SettingsRepository

        settings_repo = SettingsRepository(session_factory)
        completed_val = await settings_repo.get_app_setting("setup_completed")
        setup_completed = completed_val == "true"

        # Check whether at least one LLM provider is configured
        from flydesk.llm.repository import LLMProviderRepository

        encryption_key = config.credential_encryption_key if hasattr(config, "credential_encryption_key") else ""
        llm_repo = LLMProviderRepository(session_factory, encryption_key)
        providers = await llm_repo.list_providers()
        llm_configured = len(providers) > 0

        # Check whether a local admin user exists
        try:
            from flydesk.auth.local_user_repository import LocalUserRepository

            local_user_repo = LocalUserRepository(session_factory)
            has_admin_user = await local_user_repo.has_any_user()
        except Exception:
            logger.debug("Failed to check for admin user.", exc_info=True)

        # Check whether an SSO/OIDC provider is configured
        try:
            from flydesk.auth.repository import OIDCProviderRepository

            oidc_repo = OIDCProviderRepository(session_factory, encryption_key)
            active_provider = await oidc_repo.get_active_provider()
            has_sso_configured = active_provider is not None
        except Exception:
            logger.debug("Failed to check for SSO provider.", exc_info=True)

        # Load FQDN and locale settings
        fqdn = await settings_repo.get_app_setting("fqdn") or ""
        locale_language = await settings_repo.get_app_setting("locale_language") or ""

    # Load agent customization for display name / avatar
    agent_display_name = config.agent_name
    agent_avatar_url = ""
    if session_factory:
        try:
            agent_settings = await settings_repo.get_agent_settings()
            agent_display_name = agent_settings.display_name or agent_settings.name
            agent_avatar_url = agent_settings.avatar_url
        except Exception:
            logger.debug("Failed to load agent settings for setup status.", exc_info=True)

    return SetupStatus(
        dev_mode=config.dev_mode,
        database_configured="sqlite" not in config.database_url,
        oidc_configured=bool(config.oidc_issuer_url),
        has_seed_data=has_seed,
        setup_completed=setup_completed,
        llm_configured=llm_configured,
        has_admin_user=has_admin_user,
        has_sso_configured=has_sso_configured,
        fqdn=fqdn,
        locale_language=locale_language,
        app_title=config.app_title,
        app_version=__version__,
        agent_name=config.agent_name,
        accent_color=config.accent_color,
        agent_avatar_url=agent_avatar_url,
        agent_display_name=agent_display_name,
    )


@router.post("/create-admin")
async def create_admin_user(body: CreateAdminRequest, request: Request) -> dict:
    """Create the initial admin user during first-time setup.

    This endpoint is only available before setup is marked as completed
    and when no local users exist yet.
    """
    session_factory = getattr(request.app.state, "session_factory", None)
    if not session_factory:
        raise HTTPException(status_code=500, detail="Database not initialized")

    from flydesk.auth.local_user_repository import LocalUserRepository
    from flydesk.settings.repository import SettingsRepository

    local_user_repo = LocalUserRepository(session_factory)
    settings_repo = SettingsRepository(session_factory)

    # Guard: only works before setup_completed
    setup_done = await settings_repo.get_app_setting("setup_completed")
    if setup_done == "true":
        raise HTTPException(status_code=403, detail="Setup already completed")

    # Guard: no existing admin
    if await local_user_repo.has_any_user():
        raise HTTPException(status_code=409, detail="Admin user already exists")

    # Validate password (min 8 chars)
    if len(body.password) < 8:
        raise HTTPException(
            status_code=422, detail="Password must be at least 8 characters"
        )

    # Hash and create user with role="admin"
    from flydesk.auth.password import hash_password

    pw_hash = hash_password(body.password)
    user = await local_user_repo.create_user(
        username=body.username,
        email=body.email,
        display_name=body.display_name,
        password_hash=pw_hash,
        role="admin",
    )
    return {"success": True, "user_id": user.id}


@router.post("/configure-sso")
async def configure_sso(body: SetupSSORequest, request: Request) -> dict:
    """Configure an SSO/OIDC provider during first-time setup.

    This endpoint is only available before setup is marked as completed.
    """
    session_factory = getattr(request.app.state, "session_factory", None)
    if not session_factory:
        raise HTTPException(status_code=500, detail="Database not initialized")

    from flydesk.settings.repository import SettingsRepository

    settings_repo = SettingsRepository(session_factory)
    setup_done = await settings_repo.get_app_setting("setup_completed")
    if setup_done == "true":
        raise HTTPException(status_code=403, detail="Setup already completed")

    from flydesk.auth.repository import OIDCProviderRepository
    from flydesk.config import get_config

    config = get_config()
    oidc_repo = OIDCProviderRepository(session_factory, config.credential_encryption_key)

    provider = await oidc_repo.create_provider(
        provider_type=body.provider_type,
        display_name=body.display_name,
        issuer_url=body.issuer_url,
        client_id=body.client_id,
        client_secret=body.client_secret,
        tenant_id=body.tenant_id,
        scopes=body.scopes,
        allowed_email_domains=body.allowed_email_domains,
        is_active=True,
    )
    return {"success": True, "provider_id": provider.id}


@router.post("/test-sso")
async def test_sso_connectivity(body: TestSSORequest, request: Request) -> dict:
    """Test SSO issuer connectivity by fetching the OIDC discovery document.

    This endpoint is only available before setup is marked as completed.
    """
    session_factory = getattr(request.app.state, "session_factory", None)
    if not session_factory:
        raise HTTPException(status_code=500, detail="Database not initialized")

    from flydesk.settings.repository import SettingsRepository

    settings_repo = SettingsRepository(session_factory)
    setup_done = await settings_repo.get_app_setting("setup_completed")
    if setup_done == "true":
        raise HTTPException(status_code=403, detail="Setup already completed")

    from flydesk.auth.oidc import OIDCClient

    client = OIDCClient(issuer_url=body.issuer_url, client_id="test", client_secret="")
    try:
        discovery = await client.discover()
        return {
            "reachable": True,
            "issuer": discovery.issuer,
            "authorization_endpoint": discovery.authorization_endpoint,
            "token_endpoint": discovery.token_endpoint,
        }
    except Exception as exc:
        return {"reachable": False, "error": str(exc)}


@router.post("/configure-fqdn")
async def configure_fqdn(body: SetupFQDNRequest, request: Request) -> dict:
    """Configure the Fully Qualified Domain Name during first-time setup.

    This endpoint is only available before setup is marked as completed.
    """
    session_factory = getattr(request.app.state, "session_factory", None)
    if not session_factory:
        raise HTTPException(status_code=500, detail="Database not initialized")

    from flydesk.settings.repository import SettingsRepository

    settings_repo = SettingsRepository(session_factory)
    setup_done = await settings_repo.get_app_setting("setup_completed")
    if setup_done == "true":
        raise HTTPException(status_code=403, detail="Setup already completed")

    await settings_repo.set_app_setting("fqdn", body.fqdn, category="deployment")
    await settings_repo.set_app_setting("protocol", body.protocol, category="deployment")
    return {"success": True, "base_url": f"{body.protocol}://{body.fqdn}"}


@router.post("/configure-locale")
async def configure_locale(body: SetupLocaleRequest, request: Request) -> dict:
    """Configure locale settings during first-time setup.

    This endpoint is only available before setup is marked as completed.
    """
    session_factory = getattr(request.app.state, "session_factory", None)
    if not session_factory:
        raise HTTPException(status_code=500, detail="Database not initialized")

    from flydesk.settings.repository import SettingsRepository

    settings_repo = SettingsRepository(session_factory)
    setup_done = await settings_repo.get_app_setting("setup_completed")
    if setup_done == "true":
        raise HTTPException(status_code=403, detail="Setup already completed")

    await settings_repo.set_app_setting("locale_language", body.language, category="locale")
    await settings_repo.set_app_setting("locale_timezone", body.timezone, category="locale")
    if body.country:
        await settings_repo.set_app_setting("locale_country", body.country, category="locale")
    return {"success": True}


@router.get("/first-run")
async def check_first_run(request: Request) -> dict:
    """Check whether this is a first-run instance."""
    try:
        session_factory = getattr(request.app.state, "session_factory", None)
        if not session_factory:
            return {"is_first_run": True}

        # Check if setup was already completed
        from flydesk.settings.repository import SettingsRepository

        settings_repo = SettingsRepository(session_factory)
        completed = await settings_repo.get_app_setting("setup_completed")
        if completed == "true":
            return {"is_first_run": False}

        from flydesk.catalog.repository import CatalogRepository

        repo = CatalogRepository(session_factory)
        systems = await repo.list_systems()
        return {"is_first_run": len(systems) == 0}
    except Exception:
        logger.warning("first-run check failed, assuming first run", exc_info=True)
        return {"is_first_run": True}


def _seed_event(
    phase: str,
    phase_label: str,
    progress: int,
    message: str,
    overall_progress: int,
    error: str | None = None,
) -> str:
    """Build a SEED_PROGRESS SSE event string."""
    data: dict = {
        "phase": phase,
        "phase_label": phase_label,
        "progress": progress,
        "message": message,
        "overall_progress": overall_progress,
    }
    if error:
        data["error"] = error
    return SSEEvent(event=SSEEventType.SEED_PROGRESS, data=data).to_sse()


async def _run_with_progress_bridge(
    coro_factory,
    phase: str,
    phase_label: str,
    start_pct: int,
    span_pct: int,
) -> AsyncGenerator[str, None]:
    """Run a coroutine that reports progress via callback, yielding SSE events.

    *coro_factory* is an async callable accepting a single ``on_progress``
    callback argument.  Progress events are bridged through an
    :class:`asyncio.Queue` so that the generator can yield them as they
    arrive.
    """
    queue: asyncio.Queue = asyncio.Queue()
    sentinel = object()

    async def on_progress(pct: int, msg: str) -> None:
        await queue.put((pct, msg))

    async def runner():
        try:
            result = await coro_factory(on_progress)
            await queue.put(sentinel)
            return result
        except Exception as exc:
            await queue.put(exc)
            return None

    task = asyncio.create_task(runner())
    while True:
        item = await queue.get()
        if item is sentinel:
            break
        if isinstance(item, Exception):
            yield _seed_event(
                phase, phase_label, 100,
                f"Error: {item}", start_pct + span_pct, error=str(item),
            )
            break
        pct, msg = item
        overall = start_pct + int(pct / 100 * span_pct)
        yield _seed_event(phase, phase_label, pct, msg, overall)
    await task


async def _stream_seed_banking(  # noqa: C901 – orchestration complexity
    body: SeedRequest,
    *,
    session_factory,
    indexer,
    catalog_repo,
    skill_repo,
    knowledge_graph,
    kg_extractor,
    discovery_engine,
) -> AsyncGenerator[str, None]:
    """Async generator that orchestrates all seed phases and yields SSE events."""

    completed_phases: list[str] = []
    skipped_phases: list[str] = []
    failed_phases: list[str] = []

    # ------------------------------------------------------------------
    # Phase 1 — Catalog (systems + endpoints)  0-10%
    # ------------------------------------------------------------------
    if body.include_systems:
        yield _seed_event("catalog", "Seeding Systems & Endpoints", 0, "Starting catalog seed", 0)
        try:
            from flydesk.seeds.banking import seed_banking_endpoints, seed_banking_systems

            sys_count = await seed_banking_systems(catalog_repo)
            yield _seed_event("catalog", "Seeding Systems & Endpoints", 50,
                              f"Seeded {sys_count} systems", 5)

            ep_count = await seed_banking_endpoints(catalog_repo)
            yield _seed_event("catalog", "Seeding Systems & Endpoints", 100,
                              f"Seeded {ep_count} endpoints", 10)
            completed_phases.append("catalog")
        except Exception as exc:
            logger.error("Catalog seed failed: %s", exc, exc_info=True)
            yield _seed_event("catalog", "Seeding Systems & Endpoints", 100,
                              f"Fatal error: {exc}", 10, error=str(exc))
            failed_phases.append("catalog")
            # Catalog is fatal — emit done and return
            yield SSEEvent(event=SSEEventType.DONE, data={
                "phases_completed": completed_phases,
                "phases_skipped": skipped_phases,
                "phases_failed": failed_phases,
            }).to_sse()
            return
    else:
        skipped_phases.append("catalog")
        yield _seed_event("catalog", "Seeding Systems & Endpoints", 100, "Skipped", 10)

    # ------------------------------------------------------------------
    # Phase 2 — Knowledge documents  10-40%
    # ------------------------------------------------------------------
    if body.include_knowledge:
        yield _seed_event("indexing", "Indexing Knowledge Documents", 0,
                          "Starting document indexing", 10)
        try:
            from flydesk.seeds.banking import KNOWLEDGE_DOCUMENTS

            total_docs = len(KNOWLEDGE_DOCUMENTS)
            doc_count = 0

            for idx, document in enumerate(KNOWLEDGE_DOCUMENTS):
                try:
                    await indexer.index_document(document)
                    doc_count += 1
                except Exception as doc_exc:
                    logger.warning("Failed to index document %s: %s",
                                   document.title, doc_exc)
                pct = int((idx + 1) / total_docs * 100) if total_docs else 100
                overall = 10 + int(pct / 100 * 30)
                yield _seed_event("indexing", "Indexing Knowledge Documents", pct,
                                  f"Indexed {idx + 1}/{total_docs}: {document.title}",
                                  overall)

            yield _seed_event("indexing", "Indexing Knowledge Documents", 100,
                              f"Indexed {doc_count} documents", 40)
            completed_phases.append("indexing")
        except Exception as exc:
            logger.error("Document indexing failed: %s", exc, exc_info=True)
            yield _seed_event("indexing", "Indexing Knowledge Documents", 100,
                              f"Error: {exc}", 40, error=str(exc))
            failed_phases.append("indexing")
    else:
        skipped_phases.append("indexing")
        yield _seed_event("indexing", "Indexing Knowledge Documents", 100, "Skipped", 40)

    # ------------------------------------------------------------------
    # Phase 3 — Skills  40-45%
    # ------------------------------------------------------------------
    if body.include_skills:
        yield _seed_event("skills", "Seeding Skills", 0, "Starting skill seed", 40)
        try:
            from flydesk.seeds.banking import seed_banking_skills

            skill_count = await seed_banking_skills(skill_repo)
            yield _seed_event("skills", "Seeding Skills", 100,
                              f"Seeded {skill_count} skills", 45)
            completed_phases.append("skills")
        except Exception as exc:
            logger.warning("Skill seeding failed (non-fatal): %s", exc, exc_info=True)
            yield _seed_event("skills", "Seeding Skills", 100,
                              f"Warning: {exc}", 45, error=str(exc))
            failed_phases.append("skills")
    else:
        skipped_phases.append("skills")
        yield _seed_event("skills", "Seeding Skills", 100, "Skipped", 45)

    # ------------------------------------------------------------------
    # Phase 4 — Platform documentation  45-55%
    # ------------------------------------------------------------------
    if body.include_knowledge:
        yield _seed_event("platform_docs", "Indexing Platform Documentation", 0,
                          "Starting platform docs", 45)
        try:
            from flydesk.seeds.platform_docs import seed_platform_docs

            await seed_platform_docs(indexer)
            yield _seed_event("platform_docs", "Indexing Platform Documentation", 100,
                              "Platform documentation indexed", 55)
            completed_phases.append("platform_docs")
        except Exception as exc:
            logger.warning("Platform docs seeding failed (non-fatal): %s",
                           exc, exc_info=True)
            yield _seed_event("platform_docs", "Indexing Platform Documentation", 100,
                              f"Warning: {exc}", 55, error=str(exc))
            failed_phases.append("platform_docs")
    else:
        skipped_phases.append("platform_docs")
        yield _seed_event("platform_docs", "Indexing Platform Documentation", 100,
                          "Skipped", 55)

    # ------------------------------------------------------------------
    # Phase 5 — KG recompute  55-85%
    # ------------------------------------------------------------------
    if body.include_kg and knowledge_graph is not None and kg_extractor is not None:
        yield _seed_event("kg", "Building Knowledge Graph", 0,
                          "Starting knowledge graph recompute", 55)
        try:
            from flydesk.jobs.handlers import KGRecomputeHandler

            handler = KGRecomputeHandler(catalog_repo, knowledge_graph, kg_extractor)

            async def _kg_coro(on_progress):
                return await handler.execute(
                    job_id="seed-kg", payload={}, on_progress=on_progress,
                )

            async for event in _run_with_progress_bridge(
                _kg_coro, "kg", "Building Knowledge Graph", 55, 30,
            ):
                yield event

            completed_phases.append("kg")
        except Exception as exc:
            logger.warning("KG recompute failed (non-fatal): %s", exc, exc_info=True)
            yield _seed_event("kg", "Building Knowledge Graph", 100,
                              f"Error: {exc}", 85, error=str(exc))
            failed_phases.append("kg")
    else:
        skipped_phases.append("kg")
        yield _seed_event("kg", "Building Knowledge Graph", 100, "Skipped", 85)

    # ------------------------------------------------------------------
    # Phase 6 — Process discovery  85-100%
    # ------------------------------------------------------------------
    if body.include_discovery and discovery_engine is not None:
        yield _seed_event("discovery", "Discovering Business Processes", 0,
                          "Starting process discovery", 85)
        try:
            async def _discovery_coro(on_progress):
                return await discovery_engine._analyze(
                    job_id="seed-discovery",
                    payload={"trigger": "seed"},
                    on_progress=on_progress,
                )

            async for event in _run_with_progress_bridge(
                _discovery_coro, "discovery", "Discovering Business Processes", 85, 15,
            ):
                yield event

            completed_phases.append("discovery")
        except Exception as exc:
            logger.warning("Process discovery failed (non-fatal): %s",
                           exc, exc_info=True)
            yield _seed_event("discovery", "Discovering Business Processes", 100,
                              f"Error: {exc}", 100, error=str(exc))
            failed_phases.append("discovery")
    else:
        skipped_phases.append("discovery")
        yield _seed_event("discovery", "Discovering Business Processes", 100,
                          "Skipped", 100)

    # ------------------------------------------------------------------
    # Done
    # ------------------------------------------------------------------
    yield SSEEvent(event=SSEEventType.DONE, data={
        "phases_completed": completed_phases,
        "phases_skipped": skipped_phases,
        "phases_failed": failed_phases,
    }).to_sse()


@router.post("/seed")
async def run_seed(body: SeedRequest, request: Request) -> SeedResult | StreamingResponse:
    """Seed or unseed example data for a domain.

    When *remove* is ``True`` the endpoint returns a synchronous
    :class:`SeedResult`.  Otherwise it returns a ``StreamingResponse``
    with SSE events reporting real-time progress through all pipeline
    phases.
    """
    session_factory = getattr(request.app.state, "session_factory", None)
    if not session_factory:
        return SeedResult(success=False, message="Database not initialised")

    if body.domain == "banking":
        from flydesk.api.knowledge import get_knowledge_indexer
        from flydesk.catalog.repository import CatalogRepository
        from flydesk.skills.repository import SkillRepository

        catalog_repo = CatalogRepository(session_factory)
        skill_repo = SkillRepository(session_factory)

        indexer_fn = request.app.dependency_overrides.get(
            get_knowledge_indexer, get_knowledge_indexer
        )
        indexer = indexer_fn()

        if body.remove:
            from flydesk.seeds.banking import unseed_banking_catalog

            await unseed_banking_catalog(
                catalog_repo, knowledge_indexer=indexer, skill_repo=skill_repo,
            )
            return SeedResult(success=True, message="Banking seed data removed.")

        # ---- Streaming seed path ----

        # Resolve optional KG / discovery dependencies eagerly (before
        # the generator starts) so that FastAPI dependency injection
        # values captured from `request` remain valid.
        from flydesk.api.knowledge import get_knowledge_graph

        kg_fn = request.app.dependency_overrides.get(get_knowledge_graph, None)
        knowledge_graph = kg_fn() if kg_fn else None
        kg_extractor = getattr(request.app.state, "kg_extractor", None)
        discovery_engine = getattr(request.app.state, "discovery_engine", None)

        return StreamingResponse(
            _stream_seed_banking(
                body,
                session_factory=session_factory,
                indexer=indexer,
                catalog_repo=catalog_repo,
                skill_repo=skill_repo,
                knowledge_graph=knowledge_graph,
                kg_extractor=kg_extractor,
                discovery_engine=discovery_engine,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    elif body.domain == "platform-docs":
        from flydesk.api.knowledge import get_knowledge_indexer
        from flydesk.seeds.platform_docs import seed_platform_docs, unseed_platform_docs

        indexer = request.app.dependency_overrides.get(
            get_knowledge_indexer, get_knowledge_indexer,
        )()
        if body.remove:
            await unseed_platform_docs(indexer)
            return SeedResult(success=True, message="Platform documentation removed.")
        else:
            await seed_platform_docs(indexer)
            return SeedResult(success=True, message="Platform documentation loaded.")

    else:
        return SeedResult(success=False, message=f"Unknown domain: {body.domain}")


@router.post("/configure")
async def configure_setup(body: ConfigureRequest, request: Request) -> ConfigureResult:
    """Apply configuration from the setup wizard.

    This is a programmatic alternative to the chat-driven wizard. It can
    create an LLM provider, seed demo data, and mark setup as complete.
    """
    session_factory = getattr(request.app.state, "session_factory", None)
    if not session_factory:
        return ConfigureResult(
            success=False, message="Database not initialised"
        )

    config = getattr(request.app.state, "config", None)
    details: dict = {}

    # 1. Configure LLM provider if specified
    if body.llm_provider:
        try:
            from flydesk.llm.models import LLMProvider, ProviderType
            from flydesk.llm.repository import LLMProviderRepository

            encryption_key = config.credential_encryption_key if config else ""
            repo = LLMProviderRepository(session_factory, encryption_key)

            models_list = []
            default_model = body.llm_provider.model_id
            if body.llm_provider.model_id:
                from flydesk.llm.models import LLMModel

                models_list = [
                    LLMModel(
                        id=body.llm_provider.model_id,
                        name=body.llm_provider.model_name or body.llm_provider.model_id,
                    )
                ]

            provider = LLMProvider(
                id=str(uuid.uuid4()),
                name=body.llm_provider.name,
                provider_type=ProviderType(body.llm_provider.provider_type),
                api_key=body.llm_provider.api_key,
                base_url=body.llm_provider.base_url,
                models=models_list,
                default_model=default_model,
                is_default=True,
                is_active=True,
            )
            await repo.create_provider(provider)
            details["llm_provider"] = "configured"
            logger.info("LLM provider configured via setup: %s", provider.name)
        except Exception as exc:
            logger.error("Failed to configure LLM provider: %s", exc)
            return ConfigureResult(
                success=False,
                message=f"Failed to configure LLM provider: {exc}",
            )

    # 2. Configure embedding provider and vector store if specified
    if body.embedding or body.vector_store:
        try:
            from flydesk.settings.repository import SettingsRepository

            settings_repo = SettingsRepository(session_factory)

            if body.embedding:
                emb = body.embedding
                model_str = f"{emb.provider}:{emb.model}"
                await settings_repo.set_app_setting(
                    "embedding_model", model_str, category="embedding"
                )
                if emb.api_key:
                    await settings_repo.set_app_setting(
                        "embedding_api_key", emb.api_key, category="embedding"
                    )
                if emb.base_url:
                    await settings_repo.set_app_setting(
                        "embedding_base_url", emb.base_url, category="embedding"
                    )
                await settings_repo.set_app_setting(
                    "embedding_dimensions",
                    str(emb.dimensions),
                    category="embedding",
                )
                details["embedding"] = "configured"
                logger.info(
                    "Embedding provider configured via setup: %s", model_str
                )

            if body.vector_store:
                vs = body.vector_store
                await settings_repo.set_app_setting(
                    "type", vs.type, category="vector_store"
                )
                if vs.chroma_path:
                    await settings_repo.set_app_setting(
                        "chroma_path", vs.chroma_path, category="vector_store"
                    )
                if vs.chroma_url:
                    await settings_repo.set_app_setting(
                        "chroma_url", vs.chroma_url, category="vector_store"
                    )
                if vs.pinecone_api_key:
                    await settings_repo.set_app_setting(
                        "pinecone_api_key",
                        vs.pinecone_api_key,
                        category="vector_store",
                    )
                if vs.pinecone_index_name:
                    await settings_repo.set_app_setting(
                        "pinecone_index_name",
                        vs.pinecone_index_name,
                        category="vector_store",
                    )
                if vs.pinecone_environment:
                    await settings_repo.set_app_setting(
                        "pinecone_environment",
                        vs.pinecone_environment,
                        category="vector_store",
                    )
                details["vector_store"] = "configured"
                logger.info(
                    "Vector store configured via setup: %s", vs.type
                )

            # Reinitialize the live embedding provider if embedding was set
            if body.embedding:
                from flydesk.api.settings import _reinitialize_embedding_provider

                await _reinitialize_embedding_provider(request.app, settings_repo)

        except Exception as exc:
            logger.error("Failed to configure embedding/vector store: %s", exc)
            return ConfigureResult(
                success=False,
                message=f"Failed to configure embedding/vector store: {exc}",
            )

    # 3. Seed banking data if requested
    if body.seed_data:
        try:
            from flydesk.catalog.repository import CatalogRepository
            from flydesk.seeds.banking import seed_banking_catalog
            from flydesk.skills.repository import SkillRepository

            catalog_repo = CatalogRepository(session_factory)
            skill_repo = SkillRepository(session_factory)

            # Get the knowledge indexer so banking docs get chunked and indexed
            from flydesk.api.knowledge import get_knowledge_indexer

            indexer_fn = request.app.dependency_overrides.get(
                get_knowledge_indexer, get_knowledge_indexer
            )
            indexer = indexer_fn()

            await seed_banking_catalog(
                catalog_repo, knowledge_indexer=indexer, skill_repo=skill_repo
            )
            details["seed_data"] = "loaded"

            # Also seed platform docs (idempotent)
            try:
                from flydesk.api.knowledge import get_knowledge_indexer
                from flydesk.seeds.platform_docs import seed_platform_docs

                indexer_fn = request.app.dependency_overrides.get(
                    get_knowledge_indexer, get_knowledge_indexer
                )
                indexer = indexer_fn()
                await seed_platform_docs(indexer)
                details["platform_docs"] = "loaded"
            except Exception:
                logger.debug(
                    "Platform docs seeding skipped (non-fatal).", exc_info=True
                )
        except Exception as exc:
            logger.error("Failed to seed data: %s", exc)
            return ConfigureResult(
                success=False, message=f"Failed to seed data: {exc}"
            )

    # 4. Save agent settings if provided
    if body.agent_settings:
        try:
            from flydesk.settings.models import AgentSettings
            from flydesk.settings.repository import SettingsRepository

            agent_settings_repo = SettingsRepository(session_factory)
            agent = AgentSettings(
                name=body.agent_settings.name,
                display_name=body.agent_settings.display_name,
                personality=body.agent_settings.personality,
                tone=body.agent_settings.tone,
                greeting=body.agent_settings.greeting,
            )
            await agent_settings_repo.set_agent_settings(agent)
            details["agent_settings"] = "configured"
            logger.info("Agent settings configured via setup: %s", agent.name)
        except Exception as exc:
            logger.error("Failed to save agent settings: %s", exc)
            return ConfigureResult(
                success=False,
                message=f"Failed to save agent settings: {exc}",
            )

    # 5. Trigger KG recomputation if embedding is configured and data was seeded
    if body.embedding and body.seed_data:
        job_runner = getattr(request.app.state, "job_runner", None)
        if job_runner:
            try:
                await job_runner.submit("kg_recompute", {})
                details["kg_recompute"] = "triggered"
                logger.info("KG recomputation triggered after setup")
            except Exception:
                logger.warning(
                    "Failed to trigger KG recomputation (non-fatal).",
                    exc_info=True,
                )

    # 6. Mark setup as complete
    try:
        from flydesk.settings.repository import SettingsRepository

        settings_repo = SettingsRepository(session_factory)
        now = datetime.now(timezone.utc).isoformat()
        await settings_repo.set_app_setting(
            "setup_completed", "true", category="setup"
        )
        await settings_repo.set_app_setting(
            "setup_completed_at", now, category="setup"
        )
        details["setup_completed"] = True
    except Exception as exc:
        logger.error("Failed to mark setup complete: %s", exc)
        return ConfigureResult(
            success=False,
            message=f"Failed to mark setup as complete: {exc}",
        )

    return ConfigureResult(
        success=True,
        message="Setup configuration applied successfully.",
        details=details,
    )


@router.post("/clear")
async def clear_seed_data(request: Request) -> SeedResult:
    """Remove all seed and generated data, then reset the setup wizard."""
    session_factory = getattr(request.app.state, "session_factory", None)
    if not session_factory:
        return SeedResult(success=False, message="Database not initialised")

    cleared: list[str] = []

    try:
        # ------------------------------------------------------------------
        # 1. Unseed banking catalog (existing logic)
        # ------------------------------------------------------------------
        from flydesk.catalog.repository import CatalogRepository
        from flydesk.seeds.banking import unseed_banking_catalog
        from flydesk.skills.repository import SkillRepository

        repo = CatalogRepository(session_factory)
        skill_repo = SkillRepository(session_factory)

        # Get the knowledge indexer for doc cleanup
        from flydesk.api.knowledge import get_knowledge_indexer

        indexer_fn = request.app.dependency_overrides.get(
            get_knowledge_indexer, get_knowledge_indexer
        )
        indexer = indexer_fn()

        await unseed_banking_catalog(repo, knowledge_indexer=indexer, skill_repo=skill_repo)
        cleared.append("banking catalog")

        # Also clear platform docs
        try:
            from flydesk.seeds.platform_docs import unseed_platform_docs

            await unseed_platform_docs(indexer)
            cleared.append("platform docs")
        except Exception:
            logger.debug("Platform docs removal skipped (non-fatal).", exc_info=True)

        # ------------------------------------------------------------------
        # 2. Clear KG entities & relations
        # ------------------------------------------------------------------
        from sqlalchemy import delete

        from flydesk.models.knowledge import EntityRow, RelationRow

        async with session_factory() as session:
            await session.execute(delete(RelationRow))
            await session.execute(delete(EntityRow))
            await session.commit()
        cleared.append("knowledge graph (entities + relations)")

        # ------------------------------------------------------------------
        # 3. Clear business processes (dependencies -> steps -> processes)
        # ------------------------------------------------------------------
        from flydesk.models.process import (
            BusinessProcessRow,
            ProcessDependencyRow,
            ProcessStepRow,
        )

        async with session_factory() as session:
            await session.execute(delete(ProcessDependencyRow))
            await session.execute(delete(ProcessStepRow))
            await session.execute(delete(BusinessProcessRow))
            await session.commit()
        cleared.append("business processes")

        # ------------------------------------------------------------------
        # 4. Reset setup_completed so the wizard can run again
        # ------------------------------------------------------------------
        from flydesk.settings.repository import SettingsRepository

        settings_repo = SettingsRepository(session_factory)
        await settings_repo.set_app_setting("setup_completed", "false", category="setup")
        cleared.append("setup_completed flag")

        summary = "Cleared: " + ", ".join(cleared) + "."
        return SeedResult(success=True, message=summary)
    except Exception as exc:
        logger.error("Failed to clear data: %s", exc, exc_info=True)
        return SeedResult(success=False, message=f"Failed to clear data: {exc}")


@router.post("/reset")
async def reset_setup(request: Request) -> SeedResult:
    """Reset the setup wizard state, allowing setup to run again."""
    session_factory = getattr(request.app.state, "session_factory", None)
    if not session_factory:
        return SeedResult(success=False, message="Database not initialised")

    try:
        from flydesk.settings.repository import SettingsRepository

        settings_repo = SettingsRepository(session_factory)
        await settings_repo.set_app_setting("setup_completed", "false", category="setup")
        return SeedResult(success=True, message="Setup has been reset. Refresh the page to restart the wizard.")
    except Exception as exc:
        logger.error("Failed to reset setup: %s", exc, exc_info=True)
        return SeedResult(success=False, message=f"Failed to reset setup: {exc}")


@router.post("/complete")
async def complete_setup(request: Request) -> dict:
    """Mark the initial setup as finished."""
    session_factory = getattr(request.app.state, "session_factory", None)
    if not session_factory:
        return {"success": False, "message": "Database not initialised"}

    from flydesk.settings.repository import SettingsRepository

    settings_repo = SettingsRepository(session_factory)
    now = datetime.now(timezone.utc).isoformat()
    await settings_repo.set_app_setting("setup_completed", "true", category="setup")
    await settings_repo.set_app_setting("setup_completed_at", now, category="setup")
    return {"success": True}


@router.get("/wizard-state")
async def get_wizard_state(request: Request) -> WizardState:
    """Return the current wizard step for resumption.

    Checks the settings repository for a completed setup.
    """
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory:
        try:
            from flydesk.settings.repository import SettingsRepository

            settings_repo = SettingsRepository(session_factory)
            completed = await settings_repo.get_app_setting("setup_completed")
            if completed == "true":
                return WizardState(step="completed", completed=True)
        except Exception:
            logger.debug("Failed to check setup status.", exc_info=True)

    return WizardState(step="not_started", completed=False)
