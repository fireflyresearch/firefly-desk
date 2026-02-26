# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Audit Admin REST API -- query audit trail events."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from flydesk.api.deps import get_audit_logger
from flydesk.audit.logger import AuditLogger
from flydesk.audit.models import AuditEvent
from flydesk.rbac.guards import AuditRead

router = APIRouter(prefix="/api/audit", tags=["audit"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

Logger = Annotated[AuditLogger, Depends(get_audit_logger)]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/events", dependencies=[AuditRead])
async def query_events(
    logger: Logger,
    user_id: str | None = None,
    event_type: str | None = None,
    limit: int = 50,
) -> list[AuditEvent]:
    """Query audit events with optional filters."""
    capped = min(limit, 500)
    return await logger.query(user_id=user_id, event_type=event_type, limit=capped)


@router.get("/events/{event_id}", dependencies=[AuditRead])
async def get_event_detail(event_id: str, logger: Logger) -> AuditEvent:
    """Retrieve a single audit event by ID."""
    event = await logger.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Audit event not found")
    return event
