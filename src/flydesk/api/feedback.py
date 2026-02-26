# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Feedback REST API -- submit feedback on assistant messages."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from flydesk.api.deps import get_audit_logger
from flydesk.audit.logger import AuditLogger
from flydesk.audit.models import AuditEvent, AuditEventType

router = APIRouter(prefix="/api/chat", tags=["feedback"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

AuditLog = Annotated[AuditLogger, Depends(get_audit_logger)]


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class FeedbackRating(StrEnum):
    UP = "up"
    DOWN = "down"


class FeedbackRequest(BaseModel):
    """Body for submitting feedback on a message."""

    rating: FeedbackRating
    comment: str | None = Field(default=None, max_length=2000)


class FeedbackResponse(BaseModel):
    """Acknowledgement returned after feedback is recorded."""

    message_id: str
    status: str = "recorded"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/messages/{message_id}/feedback",
    response_model=FeedbackResponse,
    status_code=201,
)
async def submit_feedback(
    message_id: str,
    body: FeedbackRequest,
    request: Request,
    audit: AuditLog,
) -> FeedbackResponse:
    """Record user feedback (thumbs up/down + optional comment) on a message.

    The feedback is stored as an audit event of type ``MESSAGE_FEEDBACK``.
    """
    user_session = getattr(request.state, "user_session", None)
    user_id = user_session.user_id if user_session else "anonymous"

    await audit.log(
        AuditEvent(
            event_type=AuditEventType.MESSAGE_FEEDBACK,
            user_id=user_id,
            action="message_feedback",
            detail={
                "message_id": message_id,
                "rating": body.rating.value,
                **({"comment": body.comment} if body.comment else {}),
            },
        )
    )

    return FeedbackResponse(message_id=message_id)
