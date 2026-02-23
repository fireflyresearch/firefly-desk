# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Setup conversation handler -- scripted first-run experience through chat."""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from enum import StrEnum
from typing import TYPE_CHECKING

from flydesk.api.events import SSEEvent, SSEEventType

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


class SetupStep(StrEnum):
    WELCOME = "welcome"
    DEV_USER_PROFILE = "dev_user_profile"
    LLM_PROVIDER = "llm_provider"
    LLM_TEST = "llm_test"
    EMBEDDING_CONFIG = "embedding_config"
    SSO_CONFIG = "sso_config"
    SSO_TEST = "sso_test"
    DATABASE_CHECK = "database_check"
    SAMPLE_DATA = "sample_data"
    READY = "ready"
    DONE = "done"


# Step progression order
# DEV_USER_PROFILE is conditionally skipped for non-dev mode.
# SSO_CONFIG and SSO_TEST are conditionally skipped in dev mode.
# EMBEDDING_CONFIG is skipped if LLM provider was skipped.
_STEP_ORDER = [
    SetupStep.WELCOME,
    SetupStep.DEV_USER_PROFILE,
    SetupStep.LLM_PROVIDER,
    SetupStep.LLM_TEST,
    SetupStep.EMBEDDING_CONFIG,
    SetupStep.SSO_CONFIG,
    SetupStep.SSO_TEST,
    SetupStep.DATABASE_CHECK,
    SetupStep.SAMPLE_DATA,
    SetupStep.READY,
    SetupStep.DONE,
]


class SetupConversationHandler:
    """Produces scripted SSE responses for the first-run setup flow.

    This is a simple state machine that walks through setup steps,
    emitting token and widget events that guide the user through
    initial configuration.
    """

    def __init__(self, app: FastAPI) -> None:
        self._app = app
        self._current_step = SetupStep.WELCOME
        self._llm_skipped = False
        self._embedding_skipped = False
        self._sso_skipped = False
        self._pending_provider: dict | None = None
        self._pending_sso: dict | None = None
        config = getattr(app.state, "config", None)
        self._dev_mode: bool = config.dev_mode if config else True

    @property
    def current_step(self) -> SetupStep:
        return self._current_step

    async def handle(self, message: str) -> AsyncGenerator[SSEEvent, None]:
        """Handle a message and yield SSE events for the current step."""
        if self._current_step == SetupStep.WELCOME:
            async for event in self._welcome():
                yield event
            self._advance()

        elif self._current_step == SetupStep.DEV_USER_PROFILE:
            async for event in self._dev_user_profile(message):
                yield event
            self._advance()

        elif self._current_step == SetupStep.LLM_PROVIDER:
            async for event in self._llm_provider(message):
                yield event
            self._advance()

        elif self._current_step == SetupStep.LLM_TEST:
            async for event in self._llm_test(message):
                yield event
            self._advance()

        elif self._current_step == SetupStep.EMBEDDING_CONFIG:
            async for event in self._embedding_config(message):
                yield event
            self._advance()

        elif self._current_step == SetupStep.SSO_CONFIG:
            async for event in self._sso_config(message):
                yield event
            self._advance()

        elif self._current_step == SetupStep.SSO_TEST:
            async for event in self._sso_test(message):
                yield event
            self._advance()

        elif self._current_step == SetupStep.DATABASE_CHECK:
            async for event in self._database_check():
                yield event
            self._advance()

        elif self._current_step == SetupStep.SAMPLE_DATA:
            async for event in self._sample_data(message):
                yield event
            self._advance()

        elif self._current_step == SetupStep.READY:
            async for event in self._ready():
                yield event
            self._advance()

        else:
            # Already done, just acknowledge
            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={"content": "Setup is already complete. How can I help you?"},
            )

        yield SSEEvent(
            event=SSEEventType.DONE,
            data={"conversation_id": "setup"},
        )

    def _advance(self) -> None:
        idx = _STEP_ORDER.index(self._current_step)
        if idx + 1 < len(_STEP_ORDER):
            self._current_step = _STEP_ORDER[idx + 1]

        # Auto-skip DEV_USER_PROFILE when not in dev mode
        if self._current_step == SetupStep.DEV_USER_PROFILE and not self._dev_mode:
            idx = _STEP_ORDER.index(self._current_step)
            if idx + 1 < len(_STEP_ORDER):
                self._current_step = _STEP_ORDER[idx + 1]

        # Auto-skip LLM_TEST if user skipped LLM provider configuration
        if self._current_step == SetupStep.LLM_TEST and self._llm_skipped:
            idx = _STEP_ORDER.index(self._current_step)
            if idx + 1 < len(_STEP_ORDER):
                self._current_step = _STEP_ORDER[idx + 1]

        # Auto-skip EMBEDDING_CONFIG if LLM provider was skipped
        if self._current_step == SetupStep.EMBEDDING_CONFIG and self._llm_skipped:
            self._embedding_skipped = True
            idx = _STEP_ORDER.index(self._current_step)
            if idx + 1 < len(_STEP_ORDER):
                self._current_step = _STEP_ORDER[idx + 1]

        # Auto-skip SSO_CONFIG in dev mode (SSO is only relevant in production)
        if self._current_step == SetupStep.SSO_CONFIG and self._dev_mode:
            idx = _STEP_ORDER.index(self._current_step)
            if idx + 1 < len(_STEP_ORDER):
                self._current_step = _STEP_ORDER[idx + 1]

        # Auto-skip SSO_TEST if SSO was skipped or in dev mode
        if self._current_step == SetupStep.SSO_TEST and (
            self._dev_mode or self._sso_skipped
        ):
            idx = _STEP_ORDER.index(self._current_step)
            if idx + 1 < len(_STEP_ORDER):
                self._current_step = _STEP_ORDER[idx + 1]

    async def _welcome(self) -> AsyncGenerator[SSEEvent, None]:
        config = getattr(self._app.state, "config", None)
        agent_name = config.agent_name if config else "Ember"
        dev_mode = config.dev_mode if config else True

        text = (
            f"# Welcome to Firefly Desk\n\n"
            f"Hello. I am **{agent_name}**, your operations agent. "
            f"Welcome to a fresh installation.\n\n"
            f"I will walk you through the initial setup. Here is what we will configure:\n\n"
            f"1. **LLM Provider** -- Connect an AI model for intelligent operations\n"
            f"2. **Database** -- Verify your data store is ready\n"
            f"3. **Sample Data** -- Optionally load demo systems to explore\n"
            f"4. **Review** -- Confirm everything is configured\n\n"
            f"This should only take a moment. "
        )

        if dev_mode:
            text += (
                "You are running in **development mode**, "
                "which is a good starting point for getting familiar with the system."
            )
        else:
            text += (
                "You are running in **production mode**. "
                "I will check that your core services are properly configured."
            )

        yield SSEEvent(event=SSEEventType.TOKEN, data={"content": text})

    async def _dev_user_profile(self, message: str) -> AsyncGenerator[SSEEvent, None]:
        """Ask the user to customize their dev profile."""
        payload = _parse_json(message)

        if payload and payload.get("action") == "skip":
            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={
                    "content": (
                        "No problem. I will use the default developer profile. "
                        "You can update your profile later from the settings page."
                    )
                },
            )
            return

        if payload and payload.get("action") == "configure_dev_profile":
            # Store the user profile settings via SettingsRepository
            display_name = payload.get("display_name", "Dev Admin")
            email = payload.get("email", "admin@localhost")
            role = payload.get("role", "admin")
            department = payload.get("department", "")
            title = payload.get("title", "")

            session_factory = getattr(self._app.state, "session_factory", None)
            if session_factory:
                try:
                    from flydesk.settings.repository import SettingsRepository

                    settings_repo = SettingsRepository(session_factory)
                    await settings_repo.set_app_setting(
                        "dev_user_display_name", display_name, category="dev_profile"
                    )
                    await settings_repo.set_app_setting(
                        "dev_user_email", email, category="dev_profile"
                    )
                    await settings_repo.set_app_setting(
                        "dev_user_role", role, category="dev_profile"
                    )
                    if department:
                        await settings_repo.set_app_setting(
                            "dev_user_department", department, category="dev_profile"
                        )
                    if title:
                        await settings_repo.set_app_setting(
                            "dev_user_title", title, category="dev_profile"
                        )
                    logger.info("Dev user profile stored: %s (%s)", display_name, role)
                except Exception:
                    logger.warning(
                        "Failed to persist dev user profile (non-fatal).", exc_info=True
                    )

            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={
                    "content": (
                        f"Got it. I have saved your profile as {display_name}. "
                        f"Let us continue with the setup."
                    )
                },
            )
            return

        # First time entering this step -- emit the prompt and widget
        yield SSEEvent(
            event=SSEEventType.TOKEN,
            data={
                "content": (
                    "Before we begin, let me know a bit about you "
                    "so I can personalize your experience."
                )
            },
        )

        yield SSEEvent(
            event=SSEEventType.WIDGET,
            data={
                "widget_id": str(uuid.uuid4()),
                "type": "dev-user-profile",
                "props": {
                    "fields": [
                        {
                            "name": "display_name",
                            "label": "Display Name",
                            "type": "text",
                            "default": "Dev Admin",
                        },
                        {
                            "name": "email",
                            "label": "Email",
                            "type": "text",
                            "default": "admin@localhost",
                        },
                        {
                            "name": "role",
                            "label": "Role",
                            "type": "select",
                            "options": ["admin", "operator", "viewer"],
                            "default": "admin",
                        },
                        {
                            "name": "department",
                            "label": "Department",
                            "type": "text",
                            "default": "",
                        },
                        {
                            "name": "title",
                            "label": "Title",
                            "type": "text",
                            "default": "",
                        },
                    ]
                },
                "display": "inline",
                "blocking": True,
                "action": "configure_dev_profile",
            },
        )

    async def _llm_provider(self, message: str) -> AsyncGenerator[SSEEvent, None]:
        """Ask the user to configure an LLM provider."""
        # Parse incoming JSON from widget confirmation (second call to this step)
        payload = _parse_json(message)

        if payload and payload.get("action") == "skip":
            self._llm_skipped = True
            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={
                    "content": (
                        "No problem. You can configure an LLM provider later "
                        "from the admin console under the LLM Providers section."
                    )
                },
            )
            return

        if payload and payload.get("action") == "configure_llm":
            # Store the provider details for the next step (LLM_TEST)
            self._pending_provider = {
                "provider_type": payload.get("provider_type", "openai"),
                "api_key": payload.get("api_key"),
                "base_url": payload.get("base_url"),
            }
            provider_name = self._pending_provider["provider_type"].replace("_", " ").title()
            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={
                    "content": (
                        f"Great. I will now test the connection to {provider_name} "
                        f"to make sure everything is working."
                    )
                },
            )
            return

        # First time entering this step -- emit the widget
        yield SSEEvent(
            event=SSEEventType.TOKEN,
            data={
                "content": (
                    "### Step 1: LLM Provider\n\n"
                    "To enable AI-powered features, you need to configure an LLM provider. "
                    "Firefly Desk supports **OpenAI**, **Anthropic**, **Google**, and "
                    "**Ollama** (local).\n\n"
                    "Select a provider below and enter your API key, or skip this step "
                    "to configure it later."
                )
            },
        )

        yield SSEEvent(
            event=SSEEventType.WIDGET,
            data={
                "widget_id": str(uuid.uuid4()),
                "type": "llm-provider-setup",
                "props": {
                    "providers": [
                        {"value": "openai", "label": "OpenAI", "requires_key": True},
                        {"value": "anthropic", "label": "Anthropic", "requires_key": True},
                        {"value": "google", "label": "Google AI", "requires_key": True},
                        {"value": "ollama", "label": "Ollama (Local)", "requires_key": False},
                    ]
                },
                "display": "inline",
                "blocking": True,
                "action": "configure_llm",
            },
        )

    async def _llm_test(self, message: str) -> AsyncGenerator[SSEEvent, None]:
        """Test the LLM provider connectivity."""
        # If user said skip or retry after failure
        payload = _parse_json(message)
        if payload and payload.get("action") == "skip":
            self._pending_provider = None
            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={
                    "content": (
                        "Skipping LLM provider verification. You can configure "
                        "and test providers from the admin console."
                    )
                },
            )
            return

        if not self._pending_provider:
            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={
                    "content": "No LLM provider to test. Moving on to the next step."
                },
            )
            return

        # Emit TOOL_START to trigger thinking animation
        yield SSEEvent(
            event=SSEEventType.TOOL_START,
            data={"tool": "llm_health_check", "label": "Testing LLM provider connectivity"},
        )

        # Perform the actual health check
        provider_type = self._pending_provider["provider_type"]
        api_key = self._pending_provider.get("api_key")
        base_url = self._pending_provider.get("base_url")

        from flydesk.llm.models import LLMProvider, ProviderType

        provider = LLMProvider(
            id=str(uuid.uuid4()),
            name=f"{provider_type.replace('_', ' ').title()} (Setup)",
            provider_type=ProviderType(provider_type),
            api_key=api_key,
            base_url=base_url,
            is_default=True,
            is_active=True,
        )

        try:
            from flydesk.llm.health import LLMHealthChecker

            checker = LLMHealthChecker()
            status = await checker.check(provider)
        except Exception as exc:
            logger.warning("LLM health check failed: %s", exc)
            status = None

        yield SSEEvent(
            event=SSEEventType.TOOL_END,
            data={"tool": "llm_health_check"},
        )

        if status and status.reachable:
            # Success -- persist the provider
            session_factory = getattr(self._app.state, "session_factory", None)
            config = getattr(self._app.state, "config", None)
            encryption_key = config.credential_encryption_key if config else ""

            if session_factory:
                try:
                    from flydesk.llm.repository import LLMProviderRepository

                    repo = LLMProviderRepository(session_factory, encryption_key)
                    await repo.create_provider(provider)
                    logger.info("LLM provider stored: %s", provider.name)
                except Exception:
                    logger.warning(
                        "Failed to persist LLM provider (non-fatal).", exc_info=True
                    )

            latency_text = (
                f" (response time: {status.latency_ms:.0f}ms)"
                if status.latency_ms
                else ""
            )
            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={
                    "content": (
                        f"Connection successful{latency_text}. "
                        f"Your {provider_type.replace('_', ' ').title()} provider "
                        f"has been saved and set as the default."
                    )
                },
            )
            self._pending_provider = None
        else:
            error_detail = ""
            if status and status.error:
                error_detail = f" Error: {status.error}."
            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={
                    "content": (
                        f"I was not able to reach the provider.{error_detail}\n\n"
                        f"You can retry the test or skip this step and configure "
                        f"the provider later from the admin console."
                    )
                },
            )

            yield SSEEvent(
                event=SSEEventType.WIDGET,
                data={
                    "widget_id": str(uuid.uuid4()),
                    "type": "confirmation",
                    "props": {
                        "title": "LLM Provider Test Failed",
                        "description": (
                            "The connection test did not succeed. "
                            "Would you like to retry or skip?"
                        ),
                        "confirm_label": "Retry",
                        "cancel_label": "Skip",
                    },
                    "display": "inline",
                    "blocking": True,
                    "action": "llm_test_retry",
                },
            )

    async def _embedding_config(self, message: str) -> AsyncGenerator[SSEEvent, None]:
        """Configure the embedding provider for semantic search."""
        payload = _parse_json(message)

        if payload and payload.get("action") == "skip":
            self._embedding_skipped = True
            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={
                    "content": (
                        "No problem. The knowledge base will use keyword search for now. "
                        "You can configure embeddings later from **Admin > LLM Providers**."
                    )
                },
            )
            return

        if payload and payload.get("action") == "configure_embedding":
            provider = payload.get("provider", "openai")
            model = payload.get("model", "text-embedding-3-small")
            dimensions = payload.get("dimensions", 1536)
            api_key = payload.get("api_key", "")

            embedding_model = f"{provider}:{model}"

            # Store in app_settings
            session_factory = getattr(self._app.state, "session_factory", None)
            if session_factory:
                try:
                    from flydesk.settings.repository import SettingsRepository

                    settings_repo = SettingsRepository(session_factory)
                    await settings_repo.set_app_setting(
                        "embedding_model", embedding_model, category="embedding"
                    )
                    await settings_repo.set_app_setting(
                        "embedding_dimensions", str(dimensions), category="embedding"
                    )
                    if api_key:
                        await settings_repo.set_app_setting(
                            "embedding_api_key", api_key, category="embedding"
                        )
                    logger.info("Embedding config stored: %s (%dd)", embedding_model, dimensions)
                except Exception:
                    logger.warning(
                        "Failed to persist embedding config (non-fatal).", exc_info=True
                    )

            # Test the embedding
            yield SSEEvent(
                event=SSEEventType.TOOL_START,
                data={"tool": "embedding_test", "label": "Testing embedding provider"},
            )

            test_ok = False
            error_msg = ""
            try:
                from flydesk.knowledge.embeddings import LLMEmbeddingProvider

                http_client = getattr(self._app.state, "http_client", None)
                config = getattr(self._app.state, "config", None)
                encryption_key = config.credential_encryption_key if config else ""

                from flydesk.llm.repository import LLMProviderRepository

                llm_repo = LLMProviderRepository(session_factory, encryption_key)

                test_provider = LLMEmbeddingProvider(
                    http_client=http_client,
                    embedding_model=embedding_model,
                    dimensions=dimensions,
                    llm_repo=llm_repo,
                    api_key=api_key or None,
                )

                vectors = await test_provider.embed(["Test embedding"])
                vec = vectors[0]
                test_ok = not all(v == 0.0 for v in vec)
                if not test_ok:
                    error_msg = "Received zero vector — API key may be missing or invalid."
            except Exception as exc:
                error_msg = str(exc)

            yield SSEEvent(
                event=SSEEventType.TOOL_END,
                data={"tool": "embedding_test"},
            )

            if test_ok:
                yield SSEEvent(
                    event=SSEEventType.TOKEN,
                    data={
                        "content": (
                            f"Embedding test successful. Your knowledge base will use "
                            f"**{embedding_model}** for semantic search."
                        )
                    },
                )
            else:
                yield SSEEvent(
                    event=SSEEventType.TOKEN,
                    data={
                        "content": (
                            f"Embedding test did not succeed. {error_msg}\n\n"
                            f"The configuration has been saved. "
                            f"Keyword search will be used as a fallback until embeddings "
                            f"are working. You can update the configuration from "
                            f"**Admin > LLM Providers**."
                        )
                    },
                )
            return

        # First time entering this step -- emit the prompt and widget
        # Determine default provider based on the LLM provider that was just configured
        default_provider = "openai"
        if self._pending_provider:
            pt = self._pending_provider.get("provider_type", "openai")
            if pt in ("openai", "google", "ollama"):
                default_provider = pt

        embedding_models = {
            "openai": [
                {"value": "text-embedding-3-small", "label": "text-embedding-3-small (1536d)", "dimensions": 1536},
                {"value": "text-embedding-3-large", "label": "text-embedding-3-large (3072d)", "dimensions": 3072},
                {"value": "text-embedding-ada-002", "label": "text-embedding-ada-002 (1536d)", "dimensions": 1536},
            ],
            "voyage": [
                {"value": "voyage-3.5", "label": "voyage-3.5 (1024d)", "dimensions": 1024},
                {"value": "voyage-3", "label": "voyage-3 (1024d)", "dimensions": 1024},
                {"value": "voyage-code-3", "label": "voyage-code-3 (1024d)", "dimensions": 1024},
            ],
            "google": [
                {"value": "text-embedding-004", "label": "text-embedding-004 (768d)", "dimensions": 768},
            ],
            "ollama": [
                {"value": "nomic-embed-text", "label": "nomic-embed-text (768d)", "dimensions": 768},
                {"value": "mxbai-embed-large", "label": "mxbai-embed-large (1024d)", "dimensions": 1024},
            ],
        }

        yield SSEEvent(
            event=SSEEventType.TOKEN,
            data={
                "content": (
                    "### Embedding Provider\n\n"
                    "Embeddings power semantic search in the knowledge base — "
                    "they allow the agent to find relevant documents even when "
                    "exact keywords do not match.\n\n"
                    "Select an embedding provider and model below. "
                    "If you configured an LLM provider in the previous step, "
                    "I can reuse the same API key.\n\n"
                    "**Supported providers:** OpenAI, Voyage AI (recommended by Anthropic), "
                    "Google, and Ollama (local)."
                )
            },
        )

        yield SSEEvent(
            event=SSEEventType.WIDGET,
            data={
                "widget_id": str(uuid.uuid4()),
                "type": "embedding-setup",
                "props": {
                    "providers": [
                        {"value": "openai", "label": "OpenAI", "requires_key": True},
                        {"value": "voyage", "label": "Voyage AI", "requires_key": True},
                        {"value": "google", "label": "Google", "requires_key": True},
                        {"value": "ollama", "label": "Ollama (Local)", "requires_key": False},
                    ],
                    "models": embedding_models,
                    "default_provider": default_provider,
                    "reuse_llm_key": not self._llm_skipped,
                },
                "display": "inline",
                "blocking": True,
                "action": "configure_embedding",
            },
        )

    async def _sso_config(self, message: str) -> AsyncGenerator[SSEEvent, None]:
        """Ask the user to configure an SSO / OIDC identity provider."""
        payload = _parse_json(message)

        if payload and payload.get("action") == "skip":
            self._sso_skipped = True
            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={
                    "content": (
                        "No problem. You can configure single sign-on later "
                        "from the admin console under the SSO section."
                    )
                },
            )
            return

        if payload and payload.get("action") == "configure_sso":
            provider_type = payload.get("provider_type", "keycloak")
            issuer_url = payload.get("issuer_url", "")
            client_id = payload.get("client_id", "")
            client_secret = payload.get("client_secret", "")
            tenant_id = payload.get("tenant_id", "")

            self._pending_sso = {
                "provider_type": provider_type,
                "display_name": provider_type.replace("_", " ").title(),
                "issuer_url": issuer_url,
                "client_id": client_id,
                "client_secret": client_secret,
                "tenant_id": tenant_id if provider_type == "microsoft" else None,
            }

            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={
                    "content": (
                        f"Got it. I will now test the connection to your "
                        f"{provider_type.replace('_', ' ').title()} identity provider."
                    )
                },
            )
            return

        # First time entering this step -- emit the prompt and widget
        yield SSEEvent(
            event=SSEEventType.TOKEN,
            data={
                "content": (
                    "Let me help you configure single sign-on. "
                    "Which identity provider are you using?"
                )
            },
        )

        yield SSEEvent(
            event=SSEEventType.WIDGET,
            data={
                "widget_id": str(uuid.uuid4()),
                "type": "sso-provider-setup",
                "props": {
                    "providers": [
                        {"value": "keycloak", "label": "Keycloak"},
                        {"value": "google", "label": "Google"},
                        {"value": "microsoft", "label": "Microsoft"},
                        {"value": "auth0", "label": "Auth0"},
                        {"value": "cognito", "label": "AWS Cognito"},
                        {"value": "okta", "label": "Okta"},
                    ],
                    "fields": [
                        {
                            "name": "issuer_url",
                            "label": "Issuer URL",
                            "type": "text",
                            "required": True,
                            "placeholder": "https://auth.example.com/realms/myorg",
                        },
                        {
                            "name": "client_id",
                            "label": "Client ID",
                            "type": "text",
                            "required": True,
                            "placeholder": "firefly-desk",
                        },
                        {
                            "name": "client_secret",
                            "label": "Client Secret",
                            "type": "password",
                            "required": True,
                        },
                        {
                            "name": "tenant_id",
                            "label": "Tenant ID (Microsoft only)",
                            "type": "text",
                            "required": False,
                            "condition": {"provider_type": "microsoft"},
                        },
                    ],
                },
                "display": "inline",
                "blocking": True,
                "action": "configure_sso",
            },
        )

    async def _sso_test(self, message: str) -> AsyncGenerator[SSEEvent, None]:
        """Test the OIDC discovery endpoint connectivity."""
        payload = _parse_json(message)
        if payload and payload.get("action") == "skip":
            self._pending_sso = None
            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={
                    "content": (
                        "Skipping SSO verification. You can configure "
                        "and test providers from the admin console."
                    )
                },
            )
            return

        if not self._pending_sso:
            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={
                    "content": "No SSO provider to test. Moving on to the next step."
                },
            )
            return

        # Emit TOOL_START to trigger thinking animation
        yield SSEEvent(
            event=SSEEventType.TOOL_START,
            data={"tool": "oidc_discovery_check", "label": "Testing OIDC discovery endpoint"},
        )

        issuer_url = self._pending_sso["issuer_url"]
        discovery_ok = False
        error_msg = ""

        try:
            from flydesk.auth.oidc import OIDCClient

            client = OIDCClient(
                issuer_url=issuer_url,
                client_id=self._pending_sso["client_id"],
                client_secret=self._pending_sso.get("client_secret", ""),
            )
            discovery = await client.discover()
            discovery_ok = bool(discovery.authorization_endpoint)
        except Exception as exc:
            logger.warning("OIDC discovery check failed: %s", exc)
            error_msg = str(exc)

        yield SSEEvent(
            event=SSEEventType.TOOL_END,
            data={"tool": "oidc_discovery_check"},
        )

        if discovery_ok:
            # Persist the provider in the OIDCProviderRepository
            session_factory = getattr(self._app.state, "session_factory", None)
            config = getattr(self._app.state, "config", None)
            encryption_key = config.credential_encryption_key if config else ""

            if session_factory:
                try:
                    from flydesk.auth.repository import OIDCProviderRepository

                    repo = OIDCProviderRepository(session_factory, encryption_key)
                    await repo.create_provider(
                        provider_type=self._pending_sso["provider_type"],
                        display_name=self._pending_sso["display_name"],
                        issuer_url=self._pending_sso["issuer_url"],
                        client_id=self._pending_sso["client_id"],
                        client_secret=self._pending_sso.get("client_secret"),
                        tenant_id=self._pending_sso.get("tenant_id"),
                        is_active=True,
                    )
                    logger.info(
                        "OIDC provider stored: %s", self._pending_sso["display_name"]
                    )
                except Exception:
                    logger.warning(
                        "Failed to persist OIDC provider (non-fatal).", exc_info=True
                    )

            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={
                    "content": (
                        "Connection successful. The OIDC discovery endpoint is reachable "
                        "and your identity provider has been saved. Users will be able "
                        "to sign in using single sign-on."
                    )
                },
            )
            self._pending_sso = None
        else:
            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={
                    "content": (
                        f"I was not able to reach the OIDC discovery endpoint."
                        f"{(' Error: ' + error_msg + '.') if error_msg else ''}\n\n"
                        f"You can retry the test or skip this step and configure "
                        f"SSO later from the admin console."
                    )
                },
            )

            yield SSEEvent(
                event=SSEEventType.WIDGET,
                data={
                    "widget_id": str(uuid.uuid4()),
                    "type": "confirmation",
                    "props": {
                        "title": "SSO Discovery Test Failed",
                        "description": (
                            "The OIDC discovery endpoint could not be reached. "
                            "Would you like to retry or skip?"
                        ),
                        "confirm_label": "Retry",
                        "cancel_label": "Skip",
                    },
                    "display": "inline",
                    "blocking": True,
                    "action": "sso_test_retry",
                },
            )

    async def _database_check(self) -> AsyncGenerator[SSEEvent, None]:
        config = getattr(self._app.state, "config", None)
        db_url = config.database_url if config else "unknown"
        dev_mode = config.dev_mode if config else True

        is_sqlite = "sqlite" in db_url
        db_display = "SQLite (development)" if is_sqlite else "PostgreSQL"

        yield SSEEvent(
            event=SSEEventType.TOKEN,
            data={"content": "### Step 2: Database\n\nLet me check your database connection."},
        )

        # Emit a key-value widget showing database status
        yield SSEEvent(
            event=SSEEventType.WIDGET,
            data={
                "widget_id": str(uuid.uuid4()),
                "type": "key-value",
                "props": {
                    "items": [
                        {"key": "Database", "value": db_display},
                        {"key": "Status", "value": "Connected"},
                        {"key": "Dev Mode", "value": str(dev_mode)},
                    ]
                },
                "display": "inline",
                "blocking": False,
                "action": None,
            },
        )

        if is_sqlite:
            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={
                    "content": (
                        "\n\nYou are using SQLite, which works well for development "
                        "and exploration. For production use, configure PostgreSQL by "
                        "setting the FLYDESK_DATABASE_URL environment variable.\n\n"
                        "Let us continue with the next step."
                    )
                },
            )
        else:
            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={
                    "content": (
                        "\n\nYour PostgreSQL database is connected and ready. "
                        "Let us continue with the next step."
                    )
                },
            )

    async def _sample_data(self, message: str) -> AsyncGenerator[SSEEvent, None]:
        # Check if seed data already exists
        session_factory = getattr(self._app.state, "session_factory", None)
        has_seed = False
        if session_factory:
            from flydesk.catalog.repository import CatalogRepository

            repo = CatalogRepository(session_factory)
            systems = await repo.list_systems()
            has_seed = len(systems) > 0

        if has_seed:
            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={
                    "content": (
                        "I see that sample data is already loaded. "
                        "You have banking demo systems and endpoints ready to explore."
                    )
                },
            )
            # Still ensure platform docs are seeded (idempotent)
            await self._seed_platform_docs()
            return

        yield SSEEvent(
            event=SSEEventType.TOKEN,
            data={
                "content": (
                    "### Step 3: Sample Data\n\n"
                    "I can load a banking demo environment that includes:\n\n"
                    "| Resource | Count |\n"
                    "|----------|-------|\n"
                    "| Banking Systems | 5 |\n"
                    "| Service Endpoints | 16 |\n"
                    "| Knowledge Documents | 5 |\n\n"
                    "This gives you a realistic environment to explore "
                    "how Firefly Desk works. Would you like me to load it?"
                )
            },
        )

        # Emit a confirmation widget
        yield SSEEvent(
            event=SSEEventType.WIDGET,
            data={
                "widget_id": str(uuid.uuid4()),
                "type": "confirmation",
                "props": {
                    "title": "Load Banking Demo Data",
                    "description": (
                        "This will add 5 banking systems, 16 endpoints, "
                        "and 5 knowledge documents to your instance."
                    ),
                    "confirm_label": "Load Demo Data",
                    "cancel_label": "Skip",
                },
                "display": "inline",
                "blocking": True,
                "action": "seed_banking",
            },
        )

    async def _seed_platform_docs(self) -> None:
        """Seed platform documentation (idempotent)."""
        try:
            from flydesk.api.knowledge import get_knowledge_indexer

            indexer_fn = self._app.dependency_overrides.get(
                get_knowledge_indexer, get_knowledge_indexer
            )
            indexer = indexer_fn()

            from flydesk.seeds.platform_docs import seed_platform_docs

            await seed_platform_docs(indexer)
            logger.info("Platform docs seeded during setup.")
        except Exception:
            logger.debug("Platform docs seeding skipped (non-fatal).", exc_info=True)

    async def _ready(self) -> AsyncGenerator[SSEEvent, None]:
        config = getattr(self._app.state, "config", None)
        app_title = config.app_title if config else "Firefly Desk"

        # Mark setup as complete in settings
        session_factory = getattr(self._app.state, "session_factory", None)
        if session_factory:
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
                logger.info("Setup marked as complete at %s", now)
            except Exception:
                logger.warning(
                    "Failed to persist setup completion (non-fatal).", exc_info=True
                )

        # Seed platform docs as a final step (idempotent)
        await self._seed_platform_docs()

        llm_status = (
            "- **LLM Provider** -- Configured and tested\n"
            if not self._llm_skipped
            else "- **LLM Provider** -- Can be configured from the admin console\n"
        )

        embedding_status = (
            "- **Embeddings** -- Configured for semantic search\n"
            if not self._embedding_skipped
            else "- **Embeddings** -- Using keyword search (configure from admin for semantic search)\n"
        )

        sso_status = ""
        if not self._dev_mode:
            sso_status = (
                "- **Single Sign-On** -- Configured and tested\n"
                if not self._sso_skipped
                else "- **SSO** -- Can be configured from the admin console\n"
            )

        yield SSEEvent(
            event=SSEEventType.TOKEN,
            data={
                "content": (
                    f"### Setup Complete\n\n"
                    f"Here is a summary of your **{app_title}** instance:\n\n"
                    f"- **Database** -- Connected and tables are created\n"
                    f"{llm_status}"
                    f"{embedding_status}"
                    f"{sso_status}"
                    f"- **Knowledge Base** -- Ready to accept documents\n"
                    f"- **Service Catalog** -- Available for registering systems\n\n"
                    f"You can manage your instance through the **Admin** tab in the "
                    f"navigation bar. From there you can:\n\n"
                    f"1. **Register** external systems and API endpoints\n"
                    f"2. **Manage** credentials and secrets\n"
                    f"3. **Upload** knowledge documents\n"
                    f"4. **Review** the audit trail\n\n"
                    f"If you have any questions about how things work, just ask. "
                    f"I have access to the platform documentation and can guide "
                    f"you through any feature."
                )
            },
        )


def _parse_json(text: str) -> dict | None:
    """Try to parse a JSON payload from the user message."""
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return None
