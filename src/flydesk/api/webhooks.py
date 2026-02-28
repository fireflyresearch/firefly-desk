# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Webhook receiver for external system callbacks into workflows."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from flydesk.api.deps import get_workflow_engine, get_workflow_repo
from flydesk.workflows.engine import WorkflowEngine
from flydesk.workflows.models import Trigger, TriggerType
from flydesk.workflows.repository import WorkflowRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

WorkflowRepo = Annotated[WorkflowRepository, Depends(get_workflow_repo)]
Engine = Annotated[WorkflowEngine, Depends(get_workflow_engine)]


@router.post("/{token}")
async def receive_webhook(
    token: str, request: Request, repo: WorkflowRepo, engine: Engine
) -> dict:
    """Receive an external webhook and resume the waiting workflow."""
    registration = await repo.get_webhook_by_token(token)
    if registration is None or registration.status != "active":
        raise HTTPException(status_code=404, detail="Webhook not found or expired")

    body = {}
    if request.headers.get("content-type", "").startswith("application/json"):
        body = await request.json()

    await repo.consume_webhook(registration.id)

    trigger = Trigger(
        trigger_type=TriggerType.WEBHOOK,
        step_index=registration.step_index,
        payload=body,
    )
    await engine.resume(registration.workflow_id, trigger)
    return {"status": "accepted"}
