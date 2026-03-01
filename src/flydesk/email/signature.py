# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Default email signature template builder.

Generates an email-safe HTML signature with Flydesk logo branding,
using ``<table>`` layout and inline styles for maximum email client
compatibility.
"""

from __future__ import annotations

import re
from html import escape

_SAFE_EMAIL_RE = re.compile(r'^[^"<>\s]+$')

# Flydesk brand colour.
_BRAND_COLOR = "#F68000"


def build_default_signature(
    agent_name: str,
    from_address: str,
    company_name: str = "Firefly Desk",
    logo_url: str | None = None,
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
    logo_url:
        Full URL to the Flydesk logo image. When ``None`` the avatar
        cell is omitted.

    Returns
    -------
    str
        A self-contained HTML snippet suitable for appending to outgoing
        email bodies.  Uses only ``<table>`` layout with inline styles
        so it renders correctly across email clients.
    """
    if not from_address:
        return ""
    if not _SAFE_EMAIL_RE.match(from_address):
        raise ValueError(f"from_address contains unsafe characters: {from_address!r}")

    safe_name = escape(agent_name)
    safe_address = escape(from_address)
    safe_company = escape(company_name)

    # Build logo cell — uses <img> tag for the Flydesk logo, with a
    # circular clip for modern clients and a fallback bgcolor for Outlook.
    if logo_url:
        safe_logo_url = escape(logo_url, quote=True)
        logo_cell = "\n".join([
            "          <!-- Logo -->",
            '          <td width="44" height="44" align="center" valign="middle"',
            '              style="width:44px;height:44px;border-radius:50%;overflow:hidden;">',
            f'            <img src="{safe_logo_url}" alt="{safe_name}"',
            '                 width="44" height="44"',
            '                 style="display:block;border-radius:50%;border:0;"',
            "            />",
            "          </td>",
        ])
    else:
        # Fallback: styled initial letter when no logo URL is available
        initial = escape(agent_name[0].upper()) if agent_name else "E"
        avatar_css = (
            "width:44px;height:44px;"
            f"border-radius:50%;background:{_BRAND_COLOR};"
            "text-align:center;line-height:44px;"
            "font-size:20px;font-weight:bold;color:white;"
            "font-family:Arial,Helvetica,sans-serif;"
        )
        logo_cell = "\n".join([
            "          <!-- Avatar fallback -->",
            '          <td width="44" height="44" align="center" valign="middle"',
            f'              bgcolor="{_BRAND_COLOR}"',
            f'              style="{avatar_css}">',
            f"            {initial}",
            "          </td>",
        ])

    # fmt: off
    return "\n".join([
        '<table cellpadding="0" cellspacing="0" border="0" width="100%"',
        '       style="border-collapse:collapse; margin-top:16px;">',
        "  <tr>",
        "    <td>",
        '      <table cellpadding="0" cellspacing="0" border="0"',
        '             style="border-collapse:collapse;">',
        "        <tr>",
        logo_cell,
        "          <!-- Spacer -->",
        '          <td width="12" style="width:12px;">&nbsp;</td>',
        "          <!-- Info -->",
        '          <td style="vertical-align:top; font-family:Arial,Helvetica,sans-serif;">',
        f'            <strong style="font-size:14px; color:#1F2937;">{safe_name}</strong><br/>',
        '            <span style="font-size:12px; color:#6B7280;">AI Assistant</span><br/>',
        f'            <a href="mailto:{safe_address}"',
        f'               style="font-size:12px; color:#F68000; text-decoration:none;">',
        f"              {safe_address}",
        "            </a><br/>",
        f'            <span style="font-size:11px; color:#9CA3AF;">{safe_company}</span>',
        "          </td>",
        "        </tr>",
        "      </table>",
        "    </td>",
        "  </tr>",
        "</table>",
    ])
    # fmt: on
