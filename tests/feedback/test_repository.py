"""Tests for FeedbackRepository aggregation logic."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from flydesk.feedback.repository import FeedbackRepository, _from_json

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_row(detail: dict | str | None = None, **overrides):
    """Create a minimal object mimicking AuditEventRow with needed attributes."""
    row = SimpleNamespace(
        id="evt-1",
        event_type="message_feedback",
        user_id="u1",
        detail=detail,
        **overrides,
    )
    return row


def _make_session_factory(rows: list):
    """Return an async_sessionmaker-like callable that yields a mock session.

    ``async_sessionmaker()`` returns an async context manager (not a coroutine),
    so we use MagicMock for the factory and wire __aenter__/__aexit__ on its
    return value.
    """
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = rows

    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)

    # The factory's return_value must be an async context manager
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock(return_value=ctx)
    return factory


# ---------------------------------------------------------------------------
# _from_json helper
# ---------------------------------------------------------------------------

class TestFromJson:
    def test_parses_json_string(self):
        assert _from_json('{"rating": "up"}') == {"rating": "up"}

    def test_returns_dict_as_is(self):
        d = {"rating": "down"}
        assert _from_json(d) is d

    def test_returns_empty_dict_for_none(self):
        assert _from_json(None) == {}

    def test_returns_list_as_is(self):
        lst = [1, 2, 3]
        assert _from_json(lst) is lst


# ---------------------------------------------------------------------------
# FeedbackRepository.get_user_feedback_summary
# ---------------------------------------------------------------------------

class TestGetUserFeedbackSummary:
    async def test_no_feedback_returns_empty(self):
        factory = _make_session_factory([])
        repo = FeedbackRepository(factory)

        summary, pos, neg = await repo.get_user_feedback_summary("u1")
        assert summary == ""
        assert pos == 0
        assert neg == 0

    async def test_positive_and_negative_counts(self):
        rows = [
            _make_row(detail={"rating": "up"}),
            _make_row(detail={"rating": "up"}),
            _make_row(detail={"rating": "down"}),
        ]
        factory = _make_session_factory(rows)
        repo = FeedbackRepository(factory)

        summary, pos, neg = await repo.get_user_feedback_summary("u1")
        assert pos == 2
        assert neg == 1
        assert "2 positive" in summary
        assert "1 negative" in summary

    async def test_categories_appear_in_summary(self):
        rows = [
            _make_row(detail={"rating": "down", "categories": ["too_verbose"]}),
            _make_row(detail={"rating": "down", "categories": ["too_verbose", "wrong_answer"]}),
        ]
        factory = _make_session_factory(rows)
        repo = FeedbackRepository(factory)

        summary, _, _ = await repo.get_user_feedback_summary("u1")
        assert "too_verbose" in summary
        assert "Negative feedback patterns" in summary

    async def test_comments_appear_in_summary(self):
        rows = [
            _make_row(detail={"rating": "down", "comment": "Could be shorter"}),
        ]
        factory = _make_session_factory(rows)
        repo = FeedbackRepository(factory)

        summary, _, _ = await repo.get_user_feedback_summary("u1")
        assert "Could be shorter" in summary
        assert "Recent user comments" in summary

    async def test_only_first_three_comments_included(self):
        rows = [
            _make_row(detail={"rating": "down", "comment": f"Comment {i}"})
            for i in range(5)
        ]
        factory = _make_session_factory(rows)
        repo = FeedbackRepository(factory)

        summary, _, _ = await repo.get_user_feedback_summary("u1")
        assert "Comment 0" in summary
        assert "Comment 2" in summary
        assert "Comment 3" not in summary

    async def test_detail_as_json_string(self):
        rows = [
            _make_row(detail=json.dumps({"rating": "up"})),
        ]
        factory = _make_session_factory(rows)
        repo = FeedbackRepository(factory)

        _, pos, neg = await repo.get_user_feedback_summary("u1")
        assert pos == 1
        assert neg == 0

    async def test_non_dict_detail_skipped(self):
        """If detail parses to a list instead of a dict, that row is skipped."""
        rows = [
            _make_row(detail=json.dumps([1, 2, 3])),
        ]
        factory = _make_session_factory(rows)
        repo = FeedbackRepository(factory)

        summary, pos, neg = await repo.get_user_feedback_summary("u1")
        # Counts are zero because the non-dict row is skipped
        assert pos == 0
        assert neg == 0

    async def test_detail_none_skipped(self):
        """Rows with detail=None are handled gracefully."""
        rows = [
            _make_row(detail=None),
        ]
        factory = _make_session_factory(rows)
        repo = FeedbackRepository(factory)

        summary, pos, neg = await repo.get_user_feedback_summary("u1")
        assert pos == 0
        assert neg == 0


# ---------------------------------------------------------------------------
# FeedbackRepository.get_feedback_context
# ---------------------------------------------------------------------------

class TestGetFeedbackContext:
    async def test_returns_empty_string_when_no_feedback(self):
        factory = _make_session_factory([])
        repo = FeedbackRepository(factory)

        result = await repo.get_feedback_context("u1")
        assert result == ""

    async def test_returns_summary_text(self):
        rows = [
            _make_row(detail={"rating": "up"}),
        ]
        factory = _make_session_factory(rows)
        repo = FeedbackRepository(factory)

        result = await repo.get_feedback_context("u1")
        assert "1 positive" in result
