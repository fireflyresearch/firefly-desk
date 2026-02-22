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

from fastapi import APIRouter, Depends, HTTPException, Request

from flydek.audit.logger import AuditLogger
from flydek.audit.models import AuditEvent

router = APIRouter(prefix="/api/audit", tags=["audit"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_audit_logger() -> AuditLogger:
    """Provide an AuditLogger instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_audit_logger must be overridden via app.dependency_overrides"
    )


async def _require_admin(request: Request) -> None:
    """Raise 403 unless the authenticated user has the 'admin' role."""
    user = getattr(request.state, "user_session", None)
    if user is None or "admin" not in user.roles:
        raise HTTPException(status_code=403, detail="Admin role required")


AdminGuard = Depends(_require_admin)
Logger = Annotated[AuditLogger, Depends(get_audit_logger)]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/events", dependencies=[AdminGuard])
async def query_events(
    logger: Logger,
    user_id: str | None = None,
    event_type: str | None = None,
    limit: int = 50,
) -> list[AuditEvent]:
    """Query audit events with optional filters."""
    return await logger.query(user_id=user_id, event_type=event_type, limit=limit)
