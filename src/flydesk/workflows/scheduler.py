# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Periodic scheduler for polling-based workflow steps."""

from __future__ import annotations

import asyncio
import logging

from flydesk.workflows.engine import WorkflowEngine
from flydesk.workflows.models import Trigger, TriggerType
from flydesk.workflows.repository import WorkflowRepository

logger = logging.getLogger(__name__)


class WorkflowScheduler:
    def __init__(
        self,
        repo: WorkflowRepository,
        engine: WorkflowEngine,
        *,
        interval_seconds: int = 30,
    ) -> None:
        self._repo = repo
        self._engine = engine
        self._interval = interval_seconds
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("WorkflowScheduler started (interval=%ds)", self._interval)

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("WorkflowScheduler stopped")

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("WorkflowScheduler tick failed")
            await asyncio.sleep(self._interval)

    async def _tick(self) -> None:
        due = await self._repo.list_due_for_poll()
        for wf in due:
            trigger = Trigger(
                trigger_type=TriggerType.POLL, step_index=wf.current_step
            )
            await self._engine.resume(wf.id, trigger)
