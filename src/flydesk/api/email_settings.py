# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Admin API for email channel configuration."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from flydesk.api.deps import get_settings_repo
from flydesk.rbac.guards import AdminSettings
from flydesk.settings.models import EmailSettings
from flydesk.settings.repository import SettingsRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings/email", tags=["email-settings"])

SettingsRepo = Annotated[SettingsRepository, Depends(get_settings_repo)]


@router.get("", dependencies=[AdminSettings])
async def get_email_settings(repo: SettingsRepo) -> dict:
    """Get current email channel settings.

    When ``signature_html`` is empty (first setup), the response includes a
    generated default Ember signature so the admin has something ready to
    customise.  The default is **not** persisted -- it only lives in the
    response.  A ``signature_is_default`` flag tells the frontend whether the
    returned signature was auto-generated.
    """
    settings = await repo.get_email_settings()
    data = settings.model_dump()

    signature_is_default = not settings.signature_html
    if signature_is_default:
        from flydesk.email.signature import build_default_signature

        data["signature_html"] = build_default_signature(
            agent_name=settings.from_display_name or "Ember",
            from_address=settings.from_address,
        )

    data["signature_is_default"] = signature_is_default
    return data


@router.get("/default-signature", dependencies=[AdminSettings])
async def get_default_signature(repo: SettingsRepo) -> dict:
    """Return the auto-generated default Ember signature.

    Used by the frontend "Reset to Default" button so the admin can
    revert their custom signature back to the branded default.  The
    signature is generated on the fly from the current email identity
    settings (display name / from address) but is **not** persisted.
    """
    settings = await repo.get_email_settings()

    from flydesk.email.signature import build_default_signature

    signature_html = build_default_signature(
        agent_name=settings.from_display_name or "Ember",
        from_address=settings.from_address,
    )
    return {"signature_html": signature_html}


@router.put("", dependencies=[AdminSettings])
async def update_email_settings(
    body: EmailSettings,
    repo: SettingsRepo,
) -> dict:
    """Update email channel settings."""
    await repo.set_email_settings(body)
    return body.model_dump()


class TestEmailRequest(BaseModel):
    to: str
    subject: str = "Test from Ember"
    body: str = "This is a test email from Ember @ Firefly Desk."


@router.post("/test", dependencies=[AdminSettings])
async def send_test_email(
    body: TestEmailRequest,
    repo: SettingsRepo,
) -> dict:
    """Send a test email using current settings."""
    settings = await repo.get_email_settings()
    if not settings.enabled:
        return {"success": False, "error": "Email is not enabled"}

    # Create adapter based on provider
    if settings.provider == "resend":
        from flydesk.email.adapters.resend_adapter import ResendEmailAdapter

        adapter = ResendEmailAdapter(api_key=settings.provider_api_key)
    elif settings.provider == "ses":
        from flydesk.email.adapters.ses_adapter import SESEmailAdapter

        adapter = SESEmailAdapter(region=settings.provider_region)
    else:
        return {"success": False, "error": f"Unknown provider: {settings.provider}"}

    from flydesk.email.models import OutboundEmail

    email = OutboundEmail(
        from_address=settings.from_address,
        from_name=settings.from_display_name,
        to=[body.to],
        subject=body.subject,
        html_body=f"<p>{body.body}</p>",
        text_body=body.body,
    )

    result = await adapter.send(email)
    return {
        "success": result.success,
        "error": result.error,
        "message_id": result.provider_message_id,
    }


@router.get("/status", dependencies=[AdminSettings])
async def get_email_status(repo: SettingsRepo) -> dict:
    """Check email provider connection status."""
    settings = await repo.get_email_settings()
    return {
        "enabled": settings.enabled,
        "provider": settings.provider,
        "from_address": settings.from_address,
        "configured": bool(settings.provider_api_key or settings.provider_region),
    }
