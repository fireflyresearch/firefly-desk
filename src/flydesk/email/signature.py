# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Default email signature template builder.

Generates an email-safe HTML signature with Ember avatar branding,
using ``<table>`` layout and inline styles for maximum email client
compatibility.
"""

from __future__ import annotations

import re
from html import escape

_SAFE_EMAIL_RE = re.compile(r'^[^"<>\s]+$')

# Ember brand gradient colours (matches EmberAvatar SVG).
_GRADIENT_START = "#F68000"
_GRADIENT_END = "#FFF9C1"

# Inline SVG of a simplified robot icon (white, designed for the avatar circle).
# Kept intentionally small so it inlines cleanly in email HTML.
_ROBOT_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 36" '
    'width="36" height="36" fill="none">'
    '<rect x="8" y="14" width="20" height="14" rx="3" fill="white"/>'
    '<rect x="14" y="8" width="8" height="8" rx="2" fill="white"/>'
    '<circle cx="13" cy="20" r="2" fill="{start}"/>'
    '<circle cx="23" cy="20" r="2" fill="{start}"/>'
    '<rect x="15" y="23" width="6" height="2" rx="1" fill="{start}"/>'
    "</svg>"
).format(start=_GRADIENT_START)


def build_default_signature(
    agent_name: str,
    from_address: str,
    company_name: str = "Firefly Desk",
) -> str:
    """Build an email-safe HTML signature block.

    Parameters
    ----------
    agent_name:
        Display name of the AI agent (e.g. ``"Ember"``).
    from_address:
        The ``From`` email address shown to recipients.
    company_name:
        Organisation name displayed beneath the address.

    Returns
    -------
    str
        A self-contained HTML snippet suitable for appending to outgoing
        email bodies.  Uses only ``<table>`` layout with inline styles
        so it renders correctly across email clients.
    """
    if not _SAFE_EMAIL_RE.match(from_address):
        raise ValueError(f"from_address contains unsafe characters: {from_address!r}")

    safe_name = escape(agent_name)
    safe_address = escape(from_address)
    safe_company = escape(company_name)

    return (
        # Horizontal rule separator
        '<table cellpadding="0" cellspacing="0" border="0" width="100%" '
        'style="border-collapse:collapse;margin-top:16px;">'
        "<tr><td>"
        # Inner signature table: avatar | text
        '<table cellpadding="0" cellspacing="0" border="0" '
        'style="border-collapse:collapse;">'
        "<tr>"
        # --- Avatar column ---
        '<td style="vertical-align:top;padding-right:12px;padding-top:8px;">'
        '<div style="'
        "width:44px;"
        "height:44px;"
        "border-radius:50%;"
        f"background:linear-gradient(135deg, {_GRADIENT_START}, {_GRADIENT_END});"
        "text-align:center;"
        "padding-top:4px;"
        '">'
        f"{_ROBOT_SVG}"
        "</div>"
        "</td>"
        # --- Text column ---
        '<td style="vertical-align:top;font-family:Arial,Helvetica,sans-serif;">'
        # Agent name (bold)
        f'<strong style="font-size:14px;color:#1F2937;">{safe_name}</strong><br/>'
        # Subtitle
        '<span style="font-size:12px;color:#6B7280;">AI Assistant</span><br/>'
        # Email as mailto link
        f'<a href="mailto:{safe_address}" '
        f'style="font-size:12px;color:#F68000;text-decoration:none;">'
        f"{safe_address}</a><br/>"
        # Company name
        f'<span style="font-size:11px;color:#9CA3AF;">{safe_company}</span>'
        "</td>"
        "</tr>"
        "</table>"
        "</td></tr>"
        "</table>"
    )
