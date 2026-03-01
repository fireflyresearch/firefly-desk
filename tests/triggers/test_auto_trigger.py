# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for AutoTriggerService -- debounced auto-triggers for KG recomputation
and process discovery."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from flydesk.triggers.auto_trigger import AutoTriggerService, DEFAULT_DEBOUNCE_SECONDS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_config():
    """DeskConfig mock with auto_analyze enabled by default."""
    config = MagicMock()
    config.auto_analyze = True
    return config


@pytest.fixture
def mock_config_disabled():
    """DeskConfig mock with auto_analyze disabled."""
    config = MagicMock()
    config.auto_analyze = False
    return config


@pytest.fixture
def mock_job_runner():
    """JobRunner mock that records submitted jobs."""
    runner = AsyncMock()
    runner.submit.return_value = MagicMock(id="job-1")
    return runner


@pytest.fixture
def trigger(mock_config, mock_job_runner):
    """AutoTriggerService with a very short debounce window for tests."""
    return AutoTriggerService(mock_config, mock_job_runner, debounce_seconds=0.05, auto_kg_extract=True)


@pytest.fixture
def trigger_disabled(mock_config_disabled, mock_job_runner):
    """AutoTriggerService with auto_analyze and auto_kg_extract disabled."""
    return AutoTriggerService(mock_config_disabled, mock_job_runner, debounce_seconds=0.05, auto_kg_extract=False)


# ---------------------------------------------------------------------------
# Tests: on_document_indexed
# ---------------------------------------------------------------------------


class TestOnDocumentIndexed:
    """Tests for the on_document_indexed event hook."""

    async def test_submits_kg_extract_single(self, trigger, mock_job_runner):
        """Documents trigger per-doc kg_extract_single immediately."""
        await trigger.on_document_indexed("doc-1")
        mock_job_runner.submit.assert_called_once_with(
            "kg_extract_single", {"document_id": "doc-1"}
        )

    async def test_no_trigger_when_disabled(self, trigger_disabled, mock_job_runner):
        """No trigger fires when auto_kg_extract is disabled."""
        await trigger_disabled.on_document_indexed("doc-1")
        mock_job_runner.submit.assert_not_called()

    async def test_each_document_gets_own_job(self, trigger, mock_job_runner):
        """Each document triggers its own kg_extract_single job (not debounced)."""
        for i in range(5):
            await trigger.on_document_indexed(f"doc-{i}")
        assert mock_job_runner.submit.call_count == 5
        for i in range(5):
            mock_job_runner.submit.assert_any_call(
                "kg_extract_single", {"document_id": f"doc-{i}"}
            )


# ---------------------------------------------------------------------------
# Tests: on_catalog_updated
# ---------------------------------------------------------------------------


class TestOnCatalogUpdated:
    """Tests for the on_catalog_updated event hook."""

    async def test_schedules_both_triggers(self, trigger, mock_job_runner):
        """Catalog updates schedule kg_recompute, process_discovery, and system_discovery."""
        await trigger.on_catalog_updated("sys-1")
        await asyncio.sleep(0.15)
        # All three trigger types should be submitted
        assert mock_job_runner.submit.call_count == 3
        submitted_types = {call.args[0] for call in mock_job_runner.submit.call_args_list}
        assert submitted_types == {"kg_recompute", "process_discovery", "system_discovery"}

    async def test_no_trigger_when_disabled(self, trigger_disabled, mock_job_runner):
        """No trigger fires when auto_analyze is disabled."""
        await trigger_disabled.on_catalog_updated("sys-1")
        await asyncio.sleep(0.15)
        mock_job_runner.submit.assert_not_called()

    async def test_debounces_rapid_catalog_updates(self, trigger, mock_job_runner):
        """Rapid catalog updates are coalesced."""
        for i in range(3):
            await trigger.on_catalog_updated(f"sys-{i}")
        await asyncio.sleep(0.15)
        # All three trigger types only once each (debounced and deduplicated via set)
        assert mock_job_runner.submit.call_count == 3


# ---------------------------------------------------------------------------
# Tests: Debounce logic
# ---------------------------------------------------------------------------


class TestDebounceLogic:
    """Tests for the internal debounce mechanism."""

    async def test_pending_triggers_cleared_after_fire(self, trigger, mock_job_runner):
        """After firing, the pending triggers set is empty."""
        await trigger.on_catalog_updated("sys-1")
        await asyncio.sleep(0.15)
        assert len(trigger._pending_triggers) == 0

    async def test_mixed_events_coalesced(self, trigger, mock_job_runner):
        """Document and catalog events within the debounce window are combined."""
        await trigger.on_document_indexed("doc-1")
        await trigger.on_catalog_updated("sys-1")
        await asyncio.sleep(0.15)
        # kg_extract_single (immediate from doc) + kg_recompute + process_discovery + system_discovery (debounced)
        assert mock_job_runner.submit.call_count == 4
        submitted = [(call.args[0], call.args[1]) for call in mock_job_runner.submit.call_args_list]
        submitted_types = {s[0] for s in submitted}
        assert submitted_types == {"kg_extract_single", "kg_recompute", "process_discovery", "system_discovery"}

    async def test_timer_reset_on_new_event(self, trigger, mock_job_runner):
        """A new catalog event resets the debounce timer."""
        await trigger.on_catalog_updated("sys-1")
        # Wait less than the debounce period
        await asyncio.sleep(0.02)
        # This should reset the timer
        await trigger.on_catalog_updated("sys-2")
        # If we waited the original time, it should not have fired yet
        await asyncio.sleep(0.04)
        mock_job_runner.submit.assert_not_called()
        # Wait for the reset timer to fire
        await asyncio.sleep(0.1)
        # kg_recompute, process_discovery, and system_discovery (debounced)
        assert mock_job_runner.submit.call_count == 3

    async def test_cancel_pending(self, trigger, mock_job_runner):
        """cancel_pending() prevents scheduled debounced triggers from firing."""
        await trigger.on_catalog_updated("sys-1")
        trigger.cancel_pending()
        await asyncio.sleep(0.15)
        mock_job_runner.submit.assert_not_called()
        assert len(trigger._pending_triggers) == 0
        assert trigger._debounce_timer is None

    async def test_fire_triggers_handles_submit_error(self, trigger, mock_job_runner):
        """_fire_triggers gracefully handles job submission errors."""
        mock_job_runner.submit.side_effect = RuntimeError("Queue full")
        # on_document_indexed catches errors internally
        await trigger.on_document_indexed("doc-1")  # Should not raise
        # Debounced triggers also handle errors gracefully
        mock_job_runner.submit.reset_mock()
        mock_job_runner.submit.side_effect = RuntimeError("Queue full")
        await trigger.on_catalog_updated("sys-1")
        await asyncio.sleep(0.15)
        assert len(trigger._pending_triggers) == 0


# ---------------------------------------------------------------------------
# Tests: Constructor and defaults
# ---------------------------------------------------------------------------


class TestConstruction:
    """Tests for AutoTriggerService construction and configuration."""

    def test_default_debounce_seconds(self, mock_config, mock_job_runner):
        """Default debounce seconds is used when not specified."""
        svc = AutoTriggerService(mock_config, mock_job_runner)
        assert svc._debounce_seconds == DEFAULT_DEBOUNCE_SECONDS

    def test_custom_debounce_seconds(self, mock_config, mock_job_runner):
        """Custom debounce seconds can be set."""
        svc = AutoTriggerService(mock_config, mock_job_runner, debounce_seconds=10.0)
        assert svc._debounce_seconds == 10.0

    def test_initial_state_clean(self, mock_config, mock_job_runner):
        """Service starts with no pending triggers and no timer."""
        svc = AutoTriggerService(mock_config, mock_job_runner)
        assert len(svc._pending_triggers) == 0
        assert svc._debounce_timer is None

    async def test_cancel_pending_on_fresh_service(self, mock_config, mock_job_runner):
        """cancel_pending() on a fresh service is a no-op."""
        svc = AutoTriggerService(mock_config, mock_job_runner)
        svc.cancel_pending()  # Should not raise
        assert svc._debounce_timer is None


# ---------------------------------------------------------------------------
# Tests: Multiple trigger cycles
# ---------------------------------------------------------------------------


class TestMultipleCycles:
    """Tests for re-using the service across multiple trigger cycles."""

    async def test_sequential_trigger_cycles(self, trigger, mock_job_runner):
        """Service can handle multiple independent trigger cycles."""
        # First cycle: immediate kg_extract_single
        await trigger.on_document_indexed("doc-1")
        assert mock_job_runner.submit.call_count == 1

        mock_job_runner.submit.reset_mock()

        # Second cycle: debounced kg_recompute + process_discovery + system_discovery
        await trigger.on_catalog_updated("sys-1")
        await asyncio.sleep(0.15)
        assert mock_job_runner.submit.call_count == 3  # kg_recompute + process_discovery + system_discovery
