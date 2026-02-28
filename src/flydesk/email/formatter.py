# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Email formatter -- converts Markdown content to email-safe HTML."""

from __future__ import annotations

import markdown

# System font stack suitable for email clients.
_FONT_STACK = (
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
    "Helvetica, Arial, sans-serif"
)

# Shared outer wrapper for all email HTML output.
_EMAIL_WRAPPER = """\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0; padding:0; background-color:#f5f5f5;">
<div style="max-width:600px; margin:0 auto; padding:24px; \
font-family:{font_stack}; font-size:15px; line-height:1.5; color:#222;">
{content}
</div>
</body>
</html>"""

# Horizontal rule that separates the body from the signature.
_SIGNATURE_HR = (
    '<hr style="border:none; border-top:1px solid #ddd; margin:24px 0 16px;">'
)


class EmailFormatter:
    """Converts Markdown content to email-safe HTML.

    The primary use case is formatting agent responses before they are sent
    as reply emails via the :class:`EmailChannelAdapter`.  It also provides
    a helper for simple notification emails.
    """

    def __init__(self) -> None:
        self._md = markdown.Markdown(
            extensions=["tables", "fenced_code"],
            output_format="html",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def format_response(
        self,
        content: str,
        *,
        signature_html: str,
        include_greeting: bool = False,
        greeting: str = "",
    ) -> str:
        """Convert a Markdown response to a full email-safe HTML document.

        Parameters
        ----------
        content:
            The agent's response in Markdown.
        signature_html:
            Pre-rendered HTML signature block (may be empty).
        include_greeting:
            Whether to prepend a greeting line above the body.
        greeting:
            The greeting text (e.g. ``"Hi Sarah,"``).  Ignored when
            *include_greeting* is ``False``.

        Returns
        -------
        str
            A complete HTML document ready to be used as an email body.
        """
        # Reset the Markdown instance so prior conversions don't leak state.
        self._md.reset()

        parts: list[str] = []

        if include_greeting and greeting:
            parts.append(f"<p>{_escape(greeting)}</p>")

        parts.append(self._md.convert(content))

        if signature_html:
            parts.append(_SIGNATURE_HR)
            parts.append(signature_html)

        inner = "\n".join(parts)
        return _wrap(inner)

    def format_notification(self, *, title: str, summary: str) -> str:
        """Build a simple notification email with a title and summary.

        Parameters
        ----------
        title:
            A short heading displayed at the top of the email.
        summary:
            A plain-text description rendered as a paragraph.
        """
        inner = f"<h2 style=\"margin:0 0 12px;\">{_escape(title)}</h2>\n<p>{_escape(summary)}</p>"
        return _wrap(inner)


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------


def _wrap(inner_html: str) -> str:
    """Wrap *inner_html* in the shared email template."""
    return _EMAIL_WRAPPER.format(font_stack=_FONT_STACK, content=inner_html)


def _escape(text: str) -> str:
    """Minimal HTML escaping for plain text injected outside of Markdown."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
