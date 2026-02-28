# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for build_default_signature."""

from __future__ import annotations

import pytest

from flydesk.email.signature import build_default_signature



class TestDefaultSignature:
    def test_contains_ember_branding(self):
        sig = build_default_signature(
            agent_name="Ember", from_address="ember@flydesk.ai"
        )
        assert "Ember" in sig
        assert "ember@flydesk.ai" in sig
        # Should have the gradient colors from EmberAvatar
        assert "#F68000" in sig or "F68000" in sig

    def test_is_valid_html_table_layout(self):
        sig = build_default_signature(
            agent_name="Ember", from_address="ember@flydesk.ai"
        )
        assert "<table" in sig  # Email-safe table layout
        assert "</table>" in sig

    def test_contains_mailto_link(self):
        sig = build_default_signature(
            agent_name="Ember", from_address="ember@flydesk.ai"
        )
        assert 'href="mailto:ember@flydesk.ai"' in sig

    def test_contains_ai_assistant_subtitle(self):
        sig = build_default_signature(
            agent_name="Ember", from_address="ember@flydesk.ai"
        )
        assert "AI Assistant" in sig

    def test_default_company_name(self):
        sig = build_default_signature(
            agent_name="Ember", from_address="ember@flydesk.ai"
        )
        assert "Firefly Desk" in sig

    def test_custom_company_name(self):
        sig = build_default_signature(
            agent_name="Ember",
            from_address="ember@flydesk.ai",
            company_name="Acme Corp",
        )
        assert "Acme Corp" in sig
        assert "Firefly Desk" not in sig

    def test_no_css_grid_or_flexbox(self):
        sig = build_default_signature(
            agent_name="Ember", from_address="ember@flydesk.ai"
        )
        lower = sig.lower()
        assert "display: flex" not in lower
        assert "display: grid" not in lower
        assert "display:flex" not in lower
        assert "display:grid" not in lower

    def test_all_styles_inline(self):
        """Signature should use inline styles only, no <style> blocks."""
        sig = build_default_signature(
            agent_name="Ember", from_address="ember@flydesk.ai"
        )
        assert "<style" not in sig

    def test_fallback_avatar_when_no_logo_url(self):
        """Without logo_url, falls back to a circular initial with brand colour."""
        sig = build_default_signature(
            agent_name="Ember", from_address="ember@flydesk.ai"
        )
        assert "border-radius" in sig
        assert 'bgcolor="#F68000"' in sig

    def test_logo_url_uses_img_tag(self):
        """When logo_url is provided, renders an <img> tag."""
        sig = build_default_signature(
            agent_name="Ember",
            from_address="ember@flydesk.ai",
            logo_url="https://example.com/logo.png",
        )
        assert '<img src="https://example.com/logo.png"' in sig
        assert 'bgcolor="#F68000"' not in sig

    def test_logo_url_is_escaped(self):
        """Logo URL containing special chars should be HTML-escaped."""
        sig = build_default_signature(
            agent_name="Ember",
            from_address="ember@flydesk.ai",
            logo_url="https://example.com/logo.png?a=1&b=2",
        )
        assert "&amp;" in sig
        assert "&b=2" not in sig  # raw & should not appear

    def test_agent_name_in_bold(self):
        sig = build_default_signature(
            agent_name="Ember", from_address="ember@flydesk.ai"
        )
        assert "<strong" in sig or "font-weight" in sig.lower()

    def test_html_special_chars_in_agent_name_are_escaped(self) -> None:
        sig = build_default_signature(
            agent_name='<script>alert(1)</script>',
            from_address="ember@flydesk.ai",
        )
        assert "<script>" not in sig
        assert "&lt;script&gt;" in sig

    def test_html_special_chars_in_company_name_are_escaped(self) -> None:
        sig = build_default_signature(
            agent_name="Ember",
            from_address="ember@flydesk.ai",
            company_name='<img onerror="alert(1)">',
        )
        assert "<img" not in sig
        assert "&lt;img" in sig

    def test_unsafe_from_address_raises(self) -> None:
        with pytest.raises(ValueError, match="unsafe characters"):
            build_default_signature(
                agent_name="Ember",
                from_address='" onclick="alert(1)"',
            )

    def test_outer_table_has_width_attribute(self) -> None:
        sig = build_default_signature(
            agent_name="Ember", from_address="ember@flydesk.ai"
        )
        assert 'width="100%"' in sig
