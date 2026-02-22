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

from flydek.api.events import SSEEvent, SSEEventType

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


class SetupStep(StrEnum):
    WELCOME = "welcome"
    LLM_PROVIDER = "llm_provider"
    LLM_TEST = "llm_test"
    DATABASE_CHECK = "database_check"
    SAMPLE_DATA = "sample_data"
    READY = "ready"
    DONE = "done"


# Step progression order
_STEP_ORDER = [
    SetupStep.WELCOME,
    SetupStep.LLM_PROVIDER,
    SetupStep.LLM_TEST,
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
        self._pending_provider: dict | None = None

    @property
    def current_step(self) -> SetupStep:
        return self._current_step

    async def handle(self, message: str) -> AsyncGenerator[SSEEvent, None]:
        """Handle a message and yield SSE events for the current step."""
        if self._current_step == SetupStep.WELCOME:
            async for event in self._welcome():
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

        # Auto-skip LLM_TEST if user skipped LLM provider configuration
        if self._current_step == SetupStep.LLM_TEST and self._llm_skipped:
            idx = _STEP_ORDER.index(self._current_step)
            if idx + 1 < len(_STEP_ORDER):
                self._current_step = _STEP_ORDER[idx + 1]

    async def _welcome(self) -> AsyncGenerator[SSEEvent, None]:
        config = getattr(self._app.state, "config", None)
        agent_name = config.agent_name if config else "Ember"
        dev_mode = config.dev_mode if config else True

        text = (
            f"Hello. I am {agent_name}, your Firefly Desk operations agent. "
            f"Welcome to a fresh installation.\n\n"
            f"I will walk you through the initial setup. There are a few things "
            f"to configure before we get started:\n\n"
            f"1. Configure an LLM provider for AI capabilities\n"
            f"2. Verify your database connection\n"
            f"3. Optionally load sample data to explore the platform\n"
            f"4. Review what is ready\n\n"
            f"This should only take a moment. "
        )

        if dev_mode:
            text += (
                "You are currently running in development mode, "
                "which is a good starting point for getting familiar with the system."
            )
        else:
            text += (
                "You are running in production mode. "
                "I will check that your core services are properly configured."
            )

        yield SSEEvent(event=SSEEventType.TOKEN, data={"content": text})

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
                    "To enable AI-powered features, you need to configure an LLM provider. "
                    "Firefly Desk supports OpenAI, Anthropic, Google, and Ollama.\n\n"
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

        from flydek.llm.models import LLMProvider, ProviderType

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
            from flydek.llm.health import LLMHealthChecker

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
                    from flydek.llm.repository import LLMProviderRepository

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

    async def _database_check(self) -> AsyncGenerator[SSEEvent, None]:
        config = getattr(self._app.state, "config", None)
        db_url = config.database_url if config else "unknown"
        dev_mode = config.dev_mode if config else True

        is_sqlite = "sqlite" in db_url
        db_display = "SQLite (development)" if is_sqlite else "PostgreSQL"

        yield SSEEvent(
            event=SSEEventType.TOKEN,
            data={"content": "Let me check your database connection."},
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
                        "setting the FLYDEK_DATABASE_URL environment variable.\n\n"
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
            from flydek.catalog.repository import CatalogRepository

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
                    "I can load the banking demo data, which includes five banking "
                    "systems, sixteen service endpoints, and five knowledge base "
                    "documents. This gives you a realistic environment to explore "
                    "how Firefly Desk works.\n\n"
                    "Would you like me to load the banking demo data?"
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
            from flydek.api.knowledge import get_knowledge_indexer

            indexer_fn = self._app.dependency_overrides.get(
                get_knowledge_indexer, get_knowledge_indexer
            )
            indexer = indexer_fn()

            from flydek.seeds.platform_docs import seed_platform_docs

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
                from flydek.settings.repository import SettingsRepository

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
            "- LLM provider is configured and tested\n"
            if not self._llm_skipped
            else "- LLM provider can be configured from the admin console\n"
        )

        yield SSEEvent(
            event=SSEEventType.TOKEN,
            data={
                "content": (
                    f"Setup is complete. Here is a summary of your {app_title} instance:\n\n"
                    f"- Database is connected and tables are created\n"
                    f"{llm_status}"
                    f"- The knowledge base is ready to accept documents\n"
                    f"- The service catalog is available for registering systems\n\n"
                    f"You can manage your instance through the admin console, "
                    f"which you will find in the navigation sidebar. From there "
                    f"you can register external systems, manage credentials, "
                    f"upload knowledge documents, and review the audit trail.\n\n"
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
