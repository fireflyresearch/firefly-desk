# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for flydesk.email.formatter."""

from __future__ import annotations

from flydesk.email.formatter import EmailFormatter


class TestFormatResponse:
    """Tests for EmailFormatter.format_response()."""

    def test_converts_markdown_bold_to_html(self) -> None:
        fmt = EmailFormatter()
        html = fmt.format_response("**Hello** world", signature_html="")
        assert "<strong>Hello</strong>" in html
        assert "world" in html

    def test_converts_markdown_italic_to_html(self) -> None:
        fmt = EmailFormatter()
        html = fmt.format_response("*italic* text", signature_html="")
        assert "<em>italic</em>" in html

    def test_converts_markdown_links(self) -> None:
        fmt = EmailFormatter()
        html = fmt.format_response("[click here](https://example.com)", signature_html="")
        assert 'href="https://example.com"' in html
        assert "click here" in html

    def test_converts_fenced_code_blocks(self) -> None:
        fmt = EmailFormatter()
        content = "```python\nprint('hello')\n```"
        html = fmt.format_response(content, signature_html="")
        assert "<code" in html
        assert "print" in html

    def test_converts_markdown_tables(self) -> None:
        fmt = EmailFormatter()
        content = "| A | B |\n|---|---|\n| 1 | 2 |"
        html = fmt.format_response(content, signature_html="")
        assert "<table>" in html
        assert "<td>" in html

    def test_appends_signature(self) -> None:
        fmt = EmailFormatter()
        sig = "<p>-- Ember, AI Assistant</p>"
        html = fmt.format_response("Done!", signature_html=sig)
        assert "Done!" in html
        assert "-- Ember" in html

    def test_signature_separated_by_hr(self) -> None:
        fmt = EmailFormatter()
        sig = "<p>-- Ember</p>"
        html = fmt.format_response("Hello", signature_html=sig)
        assert "<hr" in html

    def test_empty_signature_no_hr(self) -> None:
        fmt = EmailFormatter()
        html = fmt.format_response("Hello", signature_html="")
        assert "<hr" not in html

    def test_wraps_in_email_template_with_font_family(self) -> None:
        fmt = EmailFormatter()
        html = fmt.format_response("Test", signature_html="")
        assert "font-family" in html

    def test_wraps_in_email_template_with_max_width(self) -> None:
        fmt = EmailFormatter()
        html = fmt.format_response("Test", signature_html="")
        assert "max-width" in html

    def test_includes_greeting_when_requested(self) -> None:
        fmt = EmailFormatter()
        html = fmt.format_response(
            "Your issue is resolved.",
            signature_html="",
            include_greeting=True,
            greeting="Hi Sarah,",
        )
        assert "Hi Sarah," in html

    def test_no_greeting_by_default(self) -> None:
        fmt = EmailFormatter()
        html = fmt.format_response("Content only.", signature_html="")
        assert "Hi " not in html

    def test_reuse_same_instance_does_not_leak_state(self) -> None:
        fmt = EmailFormatter()
        fmt.format_response("**first**", signature_html="")
        html = fmt.format_response("**second**", signature_html="")
        assert "<strong>second</strong>" in html
        assert "first" not in html


class TestFormatNotification:
    """Tests for EmailFormatter.format_notification()."""

    def test_includes_title_and_summary(self) -> None:
        fmt = EmailFormatter()
        html = fmt.format_notification(title="Ticket Update", summary="Your ticket #42 was resolved.")
        assert "Ticket Update" in html
        assert "Your ticket #42 was resolved." in html

    def test_wraps_in_email_template(self) -> None:
        fmt = EmailFormatter()
        html = fmt.format_notification(title="Alert", summary="Something happened.")
        assert "font-family" in html
        assert "max-width" in html
