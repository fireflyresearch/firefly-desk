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

    def test_contains_avatar_circle(self):
        """The avatar area should render a circular element with the brand gradient."""
        sig = build_default_signature(
            agent_name="Ember", from_address="ember@flydesk.ai"
        )
        assert "border-radius" in sig
        # Second gradient stop
        assert "#FFF9C1" in sig or "FFF9C1" in sig

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
