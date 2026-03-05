"""Tests for chat input validation."""

import pytest
from pydantic import ValidationError


def test_message_accepts_normal():
    from flydesk.api.chat import ChatMessage
    msg = ChatMessage(message="Hello")
    assert msg.message == "Hello"


def test_message_rejects_over_limit():
    from flydesk.api.chat import ChatMessage
    with pytest.raises(ValidationError):
        ChatMessage(message="x" * 100_001)


def test_message_accepts_at_limit():
    from flydesk.api.chat import ChatMessage
    msg = ChatMessage(message="x" * 100_000)
    assert len(msg.message) == 100_000


def test_file_ids_accepts_up_to_20():
    from flydesk.api.chat import ChatMessage
    msg = ChatMessage(message="test", file_ids=[f"f{i}" for i in range(20)])
    assert len(msg.file_ids) == 20


def test_file_ids_rejects_over_20():
    from flydesk.api.chat import ChatMessage
    with pytest.raises(ValidationError):
        ChatMessage(message="test", file_ids=[f"f{i}" for i in range(21)])
