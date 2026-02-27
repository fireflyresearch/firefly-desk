# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Feedback aggregation repository.

Queries MESSAGE_FEEDBACK audit events to build per-user feedback summaries
that can be injected into the system prompt for adaptive agent behavior.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.models.audit import AuditEventRow


def _from_json(value: Any) -> dict | list:
    if isinstance(value, str):
        return json.loads(value)
    return value if value is not None else {}


class FeedbackRepository:
    """Aggregates user feedback from audit events into natural language summaries."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_user_feedback_summary(
        self, user_id: str, limit: int = 50
    ) -> tuple[str, int, int]:
        """Build a natural language feedback summary for a user.

        Returns:
            A tuple of (summary_text, positive_count, negative_count).
            summary_text is empty if no feedback exists.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(AuditEventRow)
                .where(
                    AuditEventRow.event_type == "message_feedback",
                    AuditEventRow.user_id == user_id,
                )
                .order_by(AuditEventRow.timestamp.desc())
                .limit(limit)
            )
            rows = result.scalars().all()

        if not rows:
            return ("", 0, 0)

        positive = 0
        negative = 0
        category_counts: Counter[str] = Counter()
        recent_comments: list[str] = []

        for row in rows:
            detail = _from_json(row.detail) if row.detail else {}
            if not isinstance(detail, dict):
                continue

            rating = detail.get("rating", "")
            if rating == "up":
                positive += 1
            elif rating == "down":
                negative += 1

            categories = detail.get("categories", [])
            if isinstance(categories, list):
                for cat in categories:
                    category_counts[cat] += 1

            comment = detail.get("comment")
            if comment and len(recent_comments) < 3:
                recent_comments.append(str(comment))

        # Build natural language summary
        parts: list[str] = []

        total = positive + negative
        parts.append(
            f"User has given {positive} positive and {negative} negative "
            f"ratings across the last {total} feedback submissions."
        )

        if category_counts:
            top_categories = category_counts.most_common(5)
            cat_strs = [f"{cat} ({count}x)" for cat, count in top_categories]
            parts.append(f"Negative feedback patterns: {', '.join(cat_strs)}.")

        if recent_comments:
            comment_strs = [f'"{c}"' for c in recent_comments]
            parts.append(f"Recent user comments: {'; '.join(comment_strs)}.")

        summary = " ".join(parts)
        return (summary, positive, negative)

    async def get_feedback_context(self, user_id: str) -> str:
        """Return a feedback summary string for prompt injection.

        Returns empty string if no feedback exists.
        """
        summary, _, _ = await self.get_user_feedback_summary(user_id)
        return summary
