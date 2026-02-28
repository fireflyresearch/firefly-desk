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
            return_value=EmailSettings(signature_html="")
        )
        mock_repo.set_email_settings = AsyncMock()

        await get_email_settings(mock_repo)

        mock_repo.set_email_settings.assert_not_awaited()
