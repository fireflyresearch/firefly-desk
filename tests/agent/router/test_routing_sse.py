"""Tests for the ROUTING SSE event type."""

from __future__ import annotations


def test_routing_event_type_exists():
    from flydesk.api.events import SSEEventType

    assert hasattr(SSEEventType, "ROUTING")
    assert SSEEventType.ROUTING == "routing"


def test_routing_event_serializes():
    from flydesk.api.events import SSEEvent, SSEEventType

    event = SSEEvent(
        event=SSEEventType.ROUTING,
        data={"tier": "fast", "model": "anthropic:claude-haiku-4-5-20251001"},
    )
    sse = event.to_sse()
    assert "event: routing" in sse
    assert '"tier": "fast"' in sse
