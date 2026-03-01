# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the email settings API (default signature injection)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from flydesk.settings.models import EmailSettings


@pytest.fixture
def mock_repo():
    repo = AsyncMock()
    return repo


class TestGetEmailSettingsDefaultSignature:
    """Verify that get_email_settings injects a default signature when empty."""

    async def test_injects_default_signature_when_empty(self, mock_repo):
        """When signature_html is empty, response should contain a generated default."""
        from flydesk.api.email_settings import get_email_settings

        mock_repo.get_email_settings = AsyncMock(
            return_value=EmailSettings(
                from_display_name="Ember",
                from_address="ember@flydesk.ai",
                signature_html="",
            )
        )

        result = await get_email_settings(mock_repo)

        assert result["signature_is_default"] is True
        assert result["signature_html"] != ""
        assert "Ember" in result["signature_html"]
        assert "ember@flydesk.ai" in result["signature_html"]
        assert "<table" in result["signature_html"]

    async def test_does_not_override_custom_signature(self, mock_repo):
        """When signature_html is already set, it should be left unchanged."""
        from flydesk.api.email_settings import get_email_settings

        custom_sig = "<p>My custom signature</p>"
        mock_repo.get_email_settings = AsyncMock(
            return_value=EmailSettings(
                from_display_name="Ember",
                from_address="ember@flydesk.ai",
                signature_html=custom_sig,
            )
        )

        result = await get_email_settings(mock_repo)

        assert result["signature_is_default"] is False
        assert result["signature_html"] == custom_sig

    async def test_uses_from_display_name_in_default(self, mock_repo):
        """Default signature should use the from_display_name, not a hardcoded value."""
        from flydesk.api.email_settings import get_email_settings

        mock_repo.get_email_settings = AsyncMock(
            return_value=EmailSettings(
                from_display_name="Sparky",
                from_address="sparky@example.com",
                signature_html="",
            )
        )

        result = await get_email_settings(mock_repo)

        assert result["signature_is_default"] is True
        assert "Sparky" in result["signature_html"]
        assert "sparky@example.com" in result["signature_html"]

    async def test_fallback_agent_name_when_display_name_empty(self, mock_repo):
        """When from_display_name is empty, should fall back to 'Ember'."""
        from flydesk.api.email_settings import get_email_settings

        mock_repo.get_email_settings = AsyncMock(
            return_value=EmailSettings(
                from_display_name="",
                from_address="support@example.com",
                signature_html="",
            )
        )

        result = await get_email_settings(mock_repo)

        assert result["signature_is_default"] is True
        assert "Ember" in result["signature_html"]

    async def test_default_not_persisted(self, mock_repo):
        """The default signature should NOT be saved back to the repo."""
        from flydesk.api.email_settings import get_email_settings

        mock_repo.get_email_settings = AsyncMock(
            return_value=EmailSettings(signature_html="", from_address="test@example.com")
        )
        mock_repo.set_email_settings = AsyncMock()

        await get_email_settings(mock_repo)

        mock_repo.set_email_settings.assert_not_awaited()


class TestGetDefaultSignature:
    """Verify the standalone default-signature endpoint."""

    async def test_returns_generated_signature(self, mock_repo):
        """Endpoint should return a generated HTML signature from current settings."""
        from flydesk.api.email_settings import get_default_signature

        mock_repo.get_email_settings = AsyncMock(
            return_value=EmailSettings(
                from_display_name="Ember",
                from_address="ember@flydesk.ai",
            )
        )

        result = await get_default_signature(mock_repo)

        assert "signature_html" in result
        assert "Ember" in result["signature_html"]
        assert "ember@flydesk.ai" in result["signature_html"]
        assert "<table" in result["signature_html"]

    async def test_uses_current_display_name(self, mock_repo):
        """Signature should reflect the current from_display_name."""
        from flydesk.api.email_settings import get_default_signature

        mock_repo.get_email_settings = AsyncMock(
            return_value=EmailSettings(
                from_display_name="Sparky",
                from_address="sparky@example.com",
            )
        )

        result = await get_default_signature(mock_repo)

        assert "Sparky" in result["signature_html"]
        assert "sparky@example.com" in result["signature_html"]

    async def test_falls_back_to_ember_when_name_empty(self, mock_repo):
        """When from_display_name is empty, should fall back to 'Ember'."""
        from flydesk.api.email_settings import get_default_signature

        mock_repo.get_email_settings = AsyncMock(
            return_value=EmailSettings(
                from_display_name="",
                from_address="support@example.com",
            )
        )

        result = await get_default_signature(mock_repo)

        assert "Ember" in result["signature_html"]

    async def test_does_not_persist(self, mock_repo):
        """The endpoint should not write anything back to the repo."""
        from flydesk.api.email_settings import get_default_signature

        mock_repo.get_email_settings = AsyncMock(
            return_value=EmailSettings(from_address="test@example.com")
        )
        mock_repo.set_email_settings = AsyncMock()

        await get_default_signature(mock_repo)

        mock_repo.set_email_settings.assert_not_awaited()
