# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""AutoTriggerService -- debounced auto-triggers for KG recomputation and process discovery.

Listens for data change events (new knowledge documents, catalog system updates)
and submits background jobs when ``auto_analyze`` is enabled in ``DeskConfig``.

Rapid changes are coalesced within a configurable debounce window so that a
burst of document imports does not spawn dozens of redundant jobs.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flydesk.config import DeskConfig
    from flydesk.jobs.runner import JobRunner

logger = logging.getLogger(__name__)

# Default debounce window in seconds.
DEFAULT_DEBOUNCE_SECONDS: float = 5.0


class AutoTriggerService:
    """Debounced trigger service for automatic KG recomputation and process discovery.

    When ``auto_analyze`` is enabled in ``DeskConfig``, data-change events
    (document indexed, catalog updated) schedule background jobs after a
    short debounce window.  Multiple rapid events within the window are
    coalesced into a single job submission.
    """

    def __init__(
        self,
        config: DeskConfig,
        job_runner: JobRunner,
        *,
        debounce_seconds: float = DEFAULT_DEBOUNCE_SECONDS,
        auto_kg_extract: bool = True,
    ) -> None:
        self._config = config
        self._job_runner = job_runner
        self._debounce_seconds = debounce_seconds
        self._auto_kg_extract = auto_kg_extract

        # Pending trigger types accumulated during the debounce window.
        self._pending_triggers: set[str] = set()

        # Handle for the debounce timer scheduled via ``loop.call_later``.
        self._debounce_timer: asyncio.TimerHandle | None = None

    # ------------------------------------------------------------------
    # Public event hooks
    # ------------------------------------------------------------------

    async def on_document_indexed(self, doc_id: str) -> None:
        """Called after a knowledge document is successfully indexed.

        Submits a per-document KG extraction job (immediate, not debounced)
        when ``auto_kg_extract`` is enabled.
        """
        if not self._auto_kg_extract:
            return
        try:
            await self._job_runner.submit("kg_extract_single", {"document_id": doc_id})
            logger.info("Auto-triggered KG extraction for document %s", doc_id)
        except Exception:
            logger.warning(
                "Failed to submit kg_extract_single for %s", doc_id, exc_info=True
            )

    async def on_catalog_updated(self, system_id: str) -> None:
        """Called after a catalog system or endpoint is created/updated.

        Schedules both ``kg_recompute`` and ``process_discovery`` jobs if
        auto-analysis is enabled.
        """
        if not self._config.auto_analyze:
            return
        logger.debug("Catalog updated: %s -- scheduling triggers", system_id)
        self._schedule_trigger("kg_recompute")
        self._schedule_trigger("process_discovery")

    # ------------------------------------------------------------------
    # Debounce logic
    # ------------------------------------------------------------------

    def _schedule_trigger(self, trigger_type: str) -> None:
        """Add *trigger_type* to the pending set and (re)start the debounce timer.

        If a timer is already running it is cancelled and restarted so that
        rapid changes within the debounce window are coalesced.
        """
        self._pending_triggers.add(trigger_type)

        if self._debounce_timer is not None:
            self._debounce_timer.cancel()

        loop = asyncio.get_event_loop()
        self._debounce_timer = loop.call_later(
            self._debounce_seconds,
            lambda: asyncio.ensure_future(self._fire_triggers()),
        )

    async def _fire_triggers(self) -> None:
        """Submit jobs for all accumulated trigger types and clear the pending set."""
        triggers = self._pending_triggers.copy()
        self._pending_triggers.clear()
        self._debounce_timer = None

        for trigger_type in sorted(triggers):
            try:
                await self._job_runner.submit(trigger_type, {})
                logger.info("Auto-trigger fired: %s", trigger_type)
            except Exception:
                logger.warning(
                    "Failed to submit auto-trigger job '%s'.",
                    trigger_type,
                    exc_info=True,
                )

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    def cancel_pending(self) -> None:
        """Cancel any pending debounce timer (called during shutdown)."""
        if self._debounce_timer is not None:
            self._debounce_timer.cancel()
            self._debounce_timer = None
        self._pending_triggers.clear()
