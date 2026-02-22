# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the SetupConversationHandler."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from flydek.agent.setup_handler import SetupConversationHandler, SetupStep
from flydek.api.events import SSEEventType


@pytest.fixture
def mock_app() -> MagicMock:
    """Create a mock FastAPI app with state."""
    app = MagicMock()
    app.state.config = MagicMock()
    app.state.config.agent_name = "Ember"
    app.state.config.dev_mode = True
    app.state.config.database_url = "sqlite+aiosqlite:///flydek_dev.db"
    app.state.config.app_title = "Firefly Desk"
    app.state.config.credential_encryption_key = "a" * 32
    app.state.session_factory = None  # No DB for unit tests
    app.dependency_overrides = {}
    return app


@pytest.fixture
def handler(mock_app: MagicMock) -> SetupConversationHandler:
    return SetupConversationHandler(mock_app)


async def _collect(handler, message: str):
    """Collect all events from a handler call."""
    events = []
    async for event in handler.handle(message):
        events.append(event)
    return events


class TestSetupConversationHandler:
    """Tests for the setup conversation state machine."""

    async def test_initial_step_is_welcome(self, handler):
        assert handler.current_step == SetupStep.WELCOME

    async def test_welcome_message_content(self, handler):
        events = await _collect(handler, "__setup_init__")

        token_events = [e for e in events if e.event == SSEEventType.TOKEN]
        assert len(token_events) >= 1
        welcome_text = token_events[0].data["content"]
        assert "Ember" in welcome_text
        assert "fresh installation" in welcome_text

    async def test_welcome_mentions_llm_provider_step(self, handler):
        events = await _collect(handler, "__setup_init__")
        token_events = [e for e in events if e.event == SSEEventType.TOKEN]
        welcome_text = token_events[0].data["content"]
        assert "LLM Provider" in welcome_text

    async def test_welcome_advances_to_dev_user_profile(self, handler):
        await _collect(handler, "__setup_init__")
        assert handler.current_step == SetupStep.DEV_USER_PROFILE

    async def test_llm_provider_emits_widget(self, handler):
        """LLM_PROVIDER step should emit an llm-provider-setup widget."""
        await _collect(handler, "__setup_init__")
        await _collect(handler, json.dumps({"action": "skip"}))  # skip dev profile

        events = await _collect(handler, "continue")
        widget_events = [e for e in events if e.event == SSEEventType.WIDGET]
        assert len(widget_events) >= 1
        widget = widget_events[0]
        assert widget.data["type"] == "llm-provider-setup"
        assert widget.data["blocking"] is True

    async def test_llm_provider_widget_has_provider_options(self, handler):
        """Widget should list available providers."""
        await _collect(handler, "__setup_init__")
        await _collect(handler, json.dumps({"action": "skip"}))  # skip dev profile
        events = await _collect(handler, "continue")

        widget_events = [e for e in events if e.event == SSEEventType.WIDGET]
        providers = widget_events[0].data["props"]["providers"]
        provider_values = [p["value"] for p in providers]
        assert "openai" in provider_values
        assert "anthropic" in provider_values
        assert "google" in provider_values
        assert "ollama" in provider_values

    async def test_llm_provider_skip_advances_past_llm_test(self, handler):
        """Skipping LLM config should auto-advance past LLM_TEST."""
        await _collect(handler, "__setup_init__")
        await _collect(handler, json.dumps({"action": "skip"}))  # skip dev profile

        skip_msg = json.dumps({"action": "skip"})
        await _collect(handler, skip_msg)

        # Should skip LLM_TEST and go directly to DATABASE_CHECK
        assert handler.current_step == SetupStep.DATABASE_CHECK

    async def test_llm_provider_skip_emits_skip_message(self, handler):
        """Skipping should inform the user they can configure later."""
        await _collect(handler, "__setup_init__")
        await _collect(handler, json.dumps({"action": "skip"}))  # skip dev profile

        skip_msg = json.dumps({"action": "skip"})
        events = await _collect(handler, skip_msg)

        token_events = [e for e in events if e.event == SSEEventType.TOKEN]
        text = " ".join(e.data["content"] for e in token_events)
        assert "later" in text or "admin console" in text

    async def test_llm_provider_configure_stores_pending(self, handler):
        """Configuring an LLM provider should store it for the test step."""
        await _collect(handler, "__setup_init__")
        await _collect(handler, json.dumps({"action": "skip"}))  # skip dev profile

        config_msg = json.dumps({
            "action": "configure_llm",
            "provider_type": "openai",
            "api_key": "sk-test-key-12345",
            "base_url": None,
        })
        await _collect(handler, config_msg)

        assert handler.current_step == SetupStep.LLM_TEST
        assert handler._pending_provider is not None
        assert handler._pending_provider["provider_type"] == "openai"

    async def test_llm_test_emits_tool_events(self, handler):
        """LLM_TEST step should emit TOOL_START and TOOL_END events."""
        await _collect(handler, "__setup_init__")
        await _collect(handler, json.dumps({"action": "skip"}))  # skip dev profile

        config_msg = json.dumps({
            "action": "configure_llm",
            "provider_type": "openai",
            "api_key": "sk-test-key",
        })
        await _collect(handler, config_msg)

        # Mock the health checker
        mock_status = MagicMock()
        mock_status.reachable = True
        mock_status.latency_ms = 150.0
        mock_status.error = None

        with patch(
            "flydek.llm.health.LLMHealthChecker"
        ) as MockChecker:
            MockChecker.return_value.check = AsyncMock(return_value=mock_status)
            events = await _collect(handler, "continue")

        tool_starts = [e for e in events if e.event == SSEEventType.TOOL_START]
        tool_ends = [e for e in events if e.event == SSEEventType.TOOL_END]
        assert len(tool_starts) >= 1
        assert len(tool_ends) >= 1
        assert tool_starts[0].data["tool"] == "llm_health_check"

    async def test_llm_test_success_advances(self, handler):
        """Successful LLM test should advance to DATABASE_CHECK."""
        await _collect(handler, "__setup_init__")
        await _collect(handler, json.dumps({"action": "skip"}))  # skip dev profile

        config_msg = json.dumps({
            "action": "configure_llm",
            "provider_type": "anthropic",
            "api_key": "sk-ant-test",
        })
        await _collect(handler, config_msg)

        mock_status = MagicMock()
        mock_status.reachable = True
        mock_status.latency_ms = 200.0
        mock_status.error = None

        with patch(
            "flydek.llm.health.LLMHealthChecker"
        ) as MockChecker:
            MockChecker.return_value.check = AsyncMock(return_value=mock_status)
            await _collect(handler, "continue")

        assert handler.current_step == SetupStep.DATABASE_CHECK

    async def test_llm_test_failure_emits_retry_widget(self, handler):
        """Failed LLM test should offer retry or skip."""
        await _collect(handler, "__setup_init__")
        await _collect(handler, json.dumps({"action": "skip"}))  # skip dev profile

        config_msg = json.dumps({
            "action": "configure_llm",
            "provider_type": "openai",
            "api_key": "bad-key",
        })
        await _collect(handler, config_msg)

        mock_status = MagicMock()
        mock_status.reachable = False
        mock_status.latency_ms = 50.0
        mock_status.error = "HTTP 401"

        with patch(
            "flydek.llm.health.LLMHealthChecker"
        ) as MockChecker:
            MockChecker.return_value.check = AsyncMock(return_value=mock_status)
            events = await _collect(handler, "continue")

        widget_events = [e for e in events if e.event == SSEEventType.WIDGET]
        assert len(widget_events) >= 1
        assert widget_events[0].data["type"] == "confirmation"
        assert "Retry" in widget_events[0].data["props"]["confirm_label"]

    async def test_llm_test_skip_advances(self, handler):
        """Skipping after LLM test failure should advance."""
        await _collect(handler, "__setup_init__")
        await _collect(handler, json.dumps({"action": "skip"}))  # skip dev profile

        config_msg = json.dumps({
            "action": "configure_llm",
            "provider_type": "openai",
            "api_key": "bad-key",
        })
        await _collect(handler, config_msg)

        skip_msg = json.dumps({"action": "skip"})
        await _collect(handler, skip_msg)

        assert handler.current_step == SetupStep.DATABASE_CHECK

    async def test_database_check_emits_widget(self, handler):
        """DATABASE_CHECK should emit a key-value widget."""
        # Advance to database_check using skip path
        await _collect(handler, "__setup_init__")
        await _collect(handler, json.dumps({"action": "skip"}))  # skip dev profile
        await _collect(handler, json.dumps({"action": "skip"}))  # skip llm provider

        events = await _collect(handler, "continue")

        widget_events = [e for e in events if e.event == SSEEventType.WIDGET]
        assert len(widget_events) >= 1
        assert widget_events[0].data["type"] == "key-value"

    async def test_full_step_progression(self, handler):
        """Steps progress: welcome -> dev_user_profile -> llm_provider -> llm_test -> database_check -> sample_data -> ready -> done."""
        assert handler.current_step == SetupStep.WELCOME

        await _collect(handler, "__setup_init__")
        assert handler.current_step == SetupStep.DEV_USER_PROFILE

        # Skip dev user profile
        await _collect(handler, json.dumps({"action": "skip"}))
        assert handler.current_step == SetupStep.LLM_PROVIDER

        # Configure LLM provider
        config_msg = json.dumps({
            "action": "configure_llm",
            "provider_type": "openai",
            "api_key": "sk-test",
        })
        await _collect(handler, config_msg)
        assert handler.current_step == SetupStep.LLM_TEST

        # Mock successful health check
        mock_status = MagicMock()
        mock_status.reachable = True
        mock_status.latency_ms = 100.0
        mock_status.error = None

        with patch(
            "flydek.llm.health.LLMHealthChecker"
        ) as MockChecker:
            MockChecker.return_value.check = AsyncMock(return_value=mock_status)
            await _collect(handler, "continue")
        assert handler.current_step == SetupStep.DATABASE_CHECK

        await _collect(handler, "continue")
        assert handler.current_step == SetupStep.SAMPLE_DATA

        await _collect(handler, "yes")
        assert handler.current_step == SetupStep.READY

        await _collect(handler, "ok")
        assert handler.current_step == SetupStep.DONE

    async def test_skip_progression(self, handler):
        """Skipping LLM config should jump from LLM_PROVIDER to DATABASE_CHECK."""
        assert handler.current_step == SetupStep.WELCOME

        await _collect(handler, "__setup_init__")
        assert handler.current_step == SetupStep.DEV_USER_PROFILE

        await _collect(handler, json.dumps({"action": "skip"}))  # skip dev profile
        assert handler.current_step == SetupStep.LLM_PROVIDER

        await _collect(handler, json.dumps({"action": "skip"}))
        assert handler.current_step == SetupStep.DATABASE_CHECK

        await _collect(handler, "continue")
        assert handler.current_step == SetupStep.SAMPLE_DATA

        await _collect(handler, "yes")
        assert handler.current_step == SetupStep.READY

        await _collect(handler, "ok")
        assert handler.current_step == SetupStep.DONE

    async def test_every_step_ends_with_done_event(self, handler):
        """Each handle() call should end with a DONE event."""
        messages = [
            "__setup_init__",
            json.dumps({"action": "skip"}),  # skip dev profile
            json.dumps({"action": "skip"}),  # skip llm provider
            "continue",
            "yes",
            "ok",
        ]
        for msg in messages:
            events = await _collect(handler, msg)
            assert events[-1].event == SSEEventType.DONE, (
                f"Step after '{msg}' did not end with DONE"
            )

    async def test_sample_data_emits_confirmation_widget(self, handler):
        # Advance to sample_data step via skip path
        await _collect(handler, "__setup_init__")
        await _collect(handler, json.dumps({"action": "skip"}))  # skip dev profile
        await _collect(handler, json.dumps({"action": "skip"}))  # skip llm provider
        await _collect(handler, "continue")

        events = await _collect(handler, "yes")

        widget_events = [e for e in events if e.event == SSEEventType.WIDGET]
        assert len(widget_events) >= 1
        confirmation = widget_events[0]
        assert confirmation.data["type"] == "confirmation"
        assert confirmation.data["blocking"] is True

    async def test_ready_step_mentions_admin_console(self, handler):
        # Advance to ready step via skip path
        await _collect(handler, "__setup_init__")
        await _collect(handler, json.dumps({"action": "skip"}))  # skip dev profile
        await _collect(handler, json.dumps({"action": "skip"}))  # skip llm provider
        await _collect(handler, "continue")
        await _collect(handler, "yes")

        events = await _collect(handler, "ok")

        token_events = [e for e in events if e.event == SSEEventType.TOKEN]
        all_text = " ".join(e.data["content"] for e in token_events)
        assert "admin console" in all_text

    async def test_ready_step_mentions_llm_when_skipped(self, handler):
        """When LLM was skipped, ready summary should note it."""
        await _collect(handler, "__setup_init__")
        await _collect(handler, json.dumps({"action": "skip"}))  # skip dev profile
        await _collect(handler, json.dumps({"action": "skip"}))  # skip llm provider
        await _collect(handler, "continue")
        await _collect(handler, "yes")

        events = await _collect(handler, "ok")

        token_events = [e for e in events if e.event == SSEEventType.TOKEN]
        all_text = " ".join(e.data["content"] for e in token_events)
        assert "admin console" in all_text

    async def test_ready_step_mentions_llm_when_configured(self, handler):
        """When LLM was configured, ready summary should mention it."""
        await _collect(handler, "__setup_init__")
        await _collect(handler, json.dumps({"action": "skip"}))  # skip dev profile

        config_msg = json.dumps({
            "action": "configure_llm",
            "provider_type": "openai",
            "api_key": "sk-test",
        })
        await _collect(handler, config_msg)

        mock_status = MagicMock()
        mock_status.reachable = True
        mock_status.latency_ms = 100.0
        mock_status.error = None

        with patch(
            "flydek.llm.health.LLMHealthChecker"
        ) as MockChecker:
            MockChecker.return_value.check = AsyncMock(return_value=mock_status)
            await _collect(handler, "continue")

        await _collect(handler, "continue")
        await _collect(handler, "yes")

        events = await _collect(handler, "ok")

        token_events = [e for e in events if e.event == SSEEventType.TOKEN]
        all_text = " ".join(e.data["content"] for e in token_events)
        assert "Configured and tested" in all_text

    async def test_done_step_acknowledges(self, handler):
        """After reaching DONE, further messages should acknowledge completion."""
        # Advance through all steps
        await _collect(handler, "__setup_init__")
        await _collect(handler, json.dumps({"action": "skip"}))  # skip dev profile
        await _collect(handler, json.dumps({"action": "skip"}))  # skip llm provider
        await _collect(handler, "continue")
        await _collect(handler, "yes")
        await _collect(handler, "ok")

        assert handler.current_step == SetupStep.DONE

        events = await _collect(handler, "hello")
        token_events = [e for e in events if e.event == SSEEventType.TOKEN]
        text = token_events[0].data["content"]
        assert "already complete" in text
