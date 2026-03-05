"""Tests for callback models: CallbackEvent, CallbackConfig, CallbackPayload."""
from __future__ import annotations

import uuid
from datetime import datetime

from flydesk.callbacks.models import CallbackConfig, CallbackEvent, CallbackPayload


class TestCallbackEvent:
    def test_event_values(self):
        """CallbackEvent has expected string values."""
        assert CallbackEvent.EMAIL_SENT == "email.sent"
        assert CallbackEvent.EMAIL_RECEIVED == "email.received"
        assert CallbackEvent.CONVERSATION_CREATED == "conversation.created"
        assert CallbackEvent.AGENT_ERROR == "agent.error"

    def test_event_is_str(self):
        """CallbackEvent members are strings (StrEnum)."""
        assert isinstance(CallbackEvent.EMAIL_SENT, str)


class TestCallbackConfig:
    def test_default_id_is_uuid(self):
        """Default id is a valid UUID4 string."""
        config = CallbackConfig()
        parsed = uuid.UUID(config.id)
        assert parsed.version == 4

    def test_default_secret_is_hex(self):
        """Default secret is a 32-char hex string (uuid4.hex)."""
        config = CallbackConfig()
        assert len(config.secret) == 32
        int(config.secret, 16)  # raises if not hex

    def test_unique_secrets_per_instance(self):
        """Each CallbackConfig gets its own unique secret."""
        c1 = CallbackConfig()
        c2 = CallbackConfig()
        assert c1.secret != c2.secret

    def test_custom_values(self):
        """Explicit values override defaults."""
        config = CallbackConfig(
            id="custom-id",
            url="https://example.com/hook",
            secret="my-secret",
            events=["email.sent", "agent.error"],
            enabled=False,
        )
        assert config.id == "custom-id"
        assert config.url == "https://example.com/hook"
        assert config.secret == "my-secret"
        assert config.events == ["email.sent", "agent.error"]
        assert config.enabled is False

    def test_serialization_round_trip(self):
        """Model can be serialized to dict and back."""
        config = CallbackConfig(
            url="https://example.com/hook",
            events=["email.sent"],
        )
        data = config.model_dump()
        restored = CallbackConfig(**data)
        assert restored.url == config.url
        assert restored.secret == config.secret
        assert restored.events == config.events

    def test_created_at_is_iso_string(self):
        """Default created_at is a parseable ISO datetime string."""
        config = CallbackConfig()
        parsed = datetime.fromisoformat(config.created_at)
        assert parsed.tzinfo is not None


class TestCallbackPayload:
    def test_payload_fields(self):
        """CallbackPayload can be constructed with event and data."""
        payload = CallbackPayload(event="email.sent", data={"to": "user@test.com"})
        assert payload.event == "email.sent"
        assert payload.data == {"to": "user@test.com"}

    def test_timestamp_auto_populated(self):
        """Default timestamp is a parseable ISO datetime."""
        payload = CallbackPayload(event="agent.error")
        parsed = datetime.fromisoformat(payload.timestamp)
        assert parsed.tzinfo is not None

    def test_default_data_is_empty_dict(self):
        """data defaults to empty dict."""
        payload = CallbackPayload(event="email.sent")
        assert payload.data == {}
