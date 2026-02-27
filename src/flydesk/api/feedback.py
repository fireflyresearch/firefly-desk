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

from flydesk.api.deps import get_audit_logger, get_feedback_repo
from flydesk.audit.logger import AuditLogger
from flydesk.audit.models import AuditEvent, AuditEventType
from flydesk.feedback.repository import FeedbackRepository

router = APIRouter(prefix="/api/chat", tags=["feedback"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

AuditLog = Annotated[AuditLogger, Depends(get_audit_logger)]
FeedbackRepo = Annotated[FeedbackRepository, Depends(get_feedback_repo)]


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class FeedbackRating(StrEnum):
    UP = "up"
    DOWN = "down"


class FeedbackCategory(StrEnum):
    INCORRECT = "incorrect"
    UNHELPFUL = "unhelpful"
    TOO_VERBOSE = "too_verbose"
    TOO_BRIEF = "too_brief"
    OFF_TOPIC = "off_topic"
    TONE_ISSUE = "tone_issue"
    FORMATTING = "formatting"


class FeedbackRequest(BaseModel):
    """Body for submitting feedback on a message."""

    rating: FeedbackRating
    categories: list[FeedbackCategory] = Field(default_factory=list)
    comment: str | None = Field(default=None, max_length=2000)


class FeedbackResponse(BaseModel):
    """Acknowledgement returned after feedback is recorded."""

    message_id: str
    status: str = "recorded"


class FeedbackSummaryResponse(BaseModel):
    """Aggregated feedback summary for the current user."""

    summary: str
    total_positive: int
    total_negative: int


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
    """Record user feedback (thumbs up/down + optional categories/comment) on a message.

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
                **({"categories": [c.value for c in body.categories]} if body.categories else {}),
                **({"comment": body.comment} if body.comment else {}),
            },
        )
    )

    return FeedbackResponse(message_id=message_id)


@router.get("/feedback/summary", response_model=FeedbackSummaryResponse)
async def get_feedback_summary(
    request: Request,
    feedback_repo: FeedbackRepo,
) -> FeedbackSummaryResponse:
    """Get aggregated feedback summary for the current user."""
    user_session = getattr(request.state, "user_session", None)
    user_id = user_session.user_id if user_session else "anonymous"

    summary, positive, negative = await feedback_repo.get_user_feedback_summary(user_id)
    return FeedbackSummaryResponse(
        summary=summary,
        total_positive=positive,
        total_negative=negative,
    )
