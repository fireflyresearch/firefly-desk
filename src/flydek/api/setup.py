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

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/setup", tags=["setup"])

logger = logging.getLogger(__name__)


class SetupStatus(BaseModel):
    """Current deployment status returned by the setup endpoint."""

    dev_mode: bool
    database_configured: bool
    oidc_configured: bool
    has_seed_data: bool
    app_title: str
    app_version: str
    agent_name: str
    accent_color: str


class SeedRequest(BaseModel):
    """Request body for seeding or removing seed data."""

    domain: str = "banking"
    remove: bool = False


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


class ConfigureRequest(BaseModel):
    """Request body for the setup wizard configure endpoint."""

    llm_provider: LLMProviderConfig | None = None
    seed_data: bool | None = None


class ConfigureResult(BaseModel):
    """Result of a configure operation."""

    success: bool
    message: str
    details: dict | None = None


class WizardState(BaseModel):
    """Current wizard state for resumption."""

    step: str
    completed: bool


@router.get("/status")
async def get_setup_status(request: Request) -> SetupStatus:
    """Return the current deployment configuration status."""
    from flydek import __version__
    from flydek.config import get_config

    config = get_config()

    # Check if there's any seed data by looking for systems
    has_seed = False
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory:
        from flydek.catalog.repository import CatalogRepository

        repo = CatalogRepository(session_factory)
        systems = await repo.list_systems()
        has_seed = len(systems) > 0

    return SetupStatus(
        dev_mode=config.dev_mode,
        database_configured="sqlite" not in config.database_url,
        oidc_configured=bool(config.oidc_issuer_url),
        has_seed_data=has_seed,
        app_title=config.app_title,
        app_version=__version__,
        agent_name=config.agent_name,
        accent_color=config.accent_color,
    )


@router.get("/first-run")
async def check_first_run(request: Request) -> dict:
    """Check whether this is a first-run instance (no seed data loaded)."""
    session_factory = getattr(request.app.state, "session_factory", None)
    if not session_factory:
        return {"is_first_run": True}

    from flydek.catalog.repository import CatalogRepository

    repo = CatalogRepository(session_factory)
    systems = await repo.list_systems()
    return {"is_first_run": len(systems) == 0}


@router.post("/seed")
async def run_seed(body: SeedRequest, request: Request) -> SeedResult:
    """Seed or unseed example data for a domain."""
    session_factory = getattr(request.app.state, "session_factory", None)
    if not session_factory:
        return SeedResult(success=False, message="Database not initialised")

    if body.domain == "banking":
        from flydek.catalog.repository import CatalogRepository

        repo = CatalogRepository(session_factory)

        if body.remove:
            from flydek.seeds.banking import unseed_banking_catalog

            await unseed_banking_catalog(repo)
            return SeedResult(success=True, message="Banking seed data removed.")
        else:
            from flydek.seeds.banking import seed_banking_catalog

            await seed_banking_catalog(repo)
            return SeedResult(success=True, message="Banking seed data loaded successfully.")

    elif body.domain == "platform-docs":
        from flydek.api.knowledge import get_knowledge_indexer
        from flydek.seeds.platform_docs import seed_platform_docs, unseed_platform_docs

        indexer = request.app.dependency_overrides.get(get_knowledge_indexer, get_knowledge_indexer)()
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
            from flydek.llm.models import LLMProvider, ProviderType
            from flydek.llm.repository import LLMProviderRepository

            encryption_key = config.credential_encryption_key if config else ""
            repo = LLMProviderRepository(session_factory, encryption_key)

            provider = LLMProvider(
                id=str(uuid.uuid4()),
                name=body.llm_provider.name,
                provider_type=ProviderType(body.llm_provider.provider_type),
                api_key=body.llm_provider.api_key,
                base_url=body.llm_provider.base_url,
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

    # 2. Seed banking data if requested
    if body.seed_data:
        try:
            from flydek.catalog.repository import CatalogRepository
            from flydek.seeds.banking import seed_banking_catalog

            catalog_repo = CatalogRepository(session_factory)
            await seed_banking_catalog(catalog_repo)
            details["seed_data"] = "loaded"

            # Also seed platform docs (idempotent)
            try:
                from flydek.api.knowledge import get_knowledge_indexer
                from flydek.seeds.platform_docs import seed_platform_docs

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

    # 3. Mark setup as complete
    try:
        from flydek.settings.repository import SettingsRepository

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


@router.get("/wizard-state")
async def get_wizard_state(request: Request) -> WizardState:
    """Return the current wizard step for resumption.

    Checks for active setup handlers in app state. If no active handler
    is found, checks the settings repository for a completed setup.
    """
    # Check for active setup handlers
    setup_handlers = getattr(request.app.state, "setup_handlers", {})
    for _conv_id, handler in setup_handlers.items():
        step = handler.current_step
        from flydek.agent.setup_handler import SetupStep

        if step == SetupStep.DONE:
            return WizardState(step=step.value, completed=True)
        return WizardState(step=step.value, completed=False)

    # No active handlers -- check if setup was previously completed
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory:
        try:
            from flydek.settings.repository import SettingsRepository

            settings_repo = SettingsRepository(session_factory)
            completed = await settings_repo.get_app_setting("setup_completed")
            if completed == "true":
                return WizardState(step="completed", completed=True)
        except Exception:
            logger.debug("Failed to check setup status.", exc_info=True)

    return WizardState(step="not_started", completed=False)
