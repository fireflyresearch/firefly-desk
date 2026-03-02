# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Admin API for email channel configuration."""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.api.deps import get_session_factory, get_settings_repo
from flydesk.rbac.guards import AdminSettings
from flydesk.settings.models import EmailSettings
from flydesk.settings.repository import SettingsRepository

SessionFactory = Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)]

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings/email", tags=["email-settings"])

SettingsRepo = Annotated[SettingsRepository, Depends(get_settings_repo)]

# Cached base64 data URI for the bundled Flydesk logo.
_default_logo_cache: str | None = None


def _default_logo_data_uri() -> str:
    """Read the bundled Flydesk logo and return it as a base64 data URI.

    The result is cached in a module global for the lifetime of the process.
    """
    global _default_logo_cache
    if _default_logo_cache is not None:
        return _default_logo_cache

    logo_path = Path(__file__).resolve().parent.parent / "static" / "flydesk-logo.png"
    if logo_path.exists():
        raw = logo_path.read_bytes()
        b64 = base64.b64encode(raw).decode()
        _default_logo_cache = f"data:image/png;base64,{b64}"
    else:
        logger.warning("Default logo not found at %s; signatures will omit the logo.", logo_path)
        _default_logo_cache = ""
    return _default_logo_cache


def _logo_url_for(settings: EmailSettings) -> str | None:
    """Return the best logo URL for signature generation.

    Priority: custom uploaded image > default Flydesk logo (base64).
    """
    if settings.signature_image_url:
        return settings.signature_image_url
    return _default_logo_data_uri() or None


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
            logo_url=_logo_url_for(settings),
        )

    data["signature_is_default"] = signature_is_default
    data["signature_image_url"] = settings.signature_image_url
    return data


@router.get("/default-signature", dependencies=[AdminSettings])
async def get_default_signature(repo: SettingsRepo) -> dict:
    """Return the auto-generated default Flydesk signature.

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
        logo_url=_logo_url_for(settings),
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
    """Send a test email using current settings, including signature."""
    settings = await repo.get_email_settings()
    if not settings.enabled:
        return {"success": False, "error": "Email is not enabled. Enable it first in General settings."}

    if not settings.provider_api_key and settings.provider != "ses":
        return {"success": False, "error": "No API key configured. Add your provider API key first."}

    if not settings.from_address:
        return {"success": False, "error": "No sender address configured. Set a From address first."}

    # Create adapter based on provider
    if settings.provider == "resend":
        from flydesk.email.adapters.resend_adapter import ResendEmailAdapter

        adapter = ResendEmailAdapter(api_key=settings.provider_api_key)
    elif settings.provider == "ses":
        from flydesk.email.adapters.ses_adapter import SESEmailAdapter

        adapter = SESEmailAdapter(region=settings.provider_region)
    else:
        return {"success": False, "error": f"Unknown provider: {settings.provider}"}

    # Build HTML body with signature (mirrors real email output)
    from flydesk.email.formatter import EmailFormatter
    from flydesk.email.models import OutboundEmail

    formatter = EmailFormatter()
    signature_html = settings.signature_html
    if not signature_html:
        from flydesk.email.signature import build_default_signature

        signature_html = build_default_signature(
            agent_name=settings.from_display_name or "Ember",
            from_address=settings.from_address,
            logo_url=_logo_url_for(settings),
        )

    html_body = formatter.format_response(body.body, signature_html=signature_html)

    email = OutboundEmail(
        from_address=settings.from_address,
        from_name=settings.from_display_name or "Ember",
        to=[body.to],
        subject=body.subject,
        html_body=html_body,
        text_body=body.body,
    )

    result = await adapter.send(email)

    if not result.success:
        error = result.error or "Unknown error"
        if "401" in error or "unauthorized" in error.lower():
            error = "Invalid API key. Check your Resend API key."
        elif "403" in error or "forbidden" in error.lower():
            error = f"Sender address not verified. Verify '{settings.from_address}' in your Resend dashboard."
        elif "422" in error:
            error = f"Invalid request. Check that '{settings.from_address}' is a valid sender."
        elif "timeout" in error.lower() or "connect" in error.lower():
            error = "Connection failed. Check your network and try again."

    return {
        "success": result.success,
        "error": result.error if not result.success else None,
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


@router.post("/validate", dependencies=[AdminSettings])
async def validate_connection(repo: SettingsRepo) -> dict:
    """Validate email provider credentials by making a lightweight API call.

    For Resend this lists domains (no email sent).
    For SES this calls GetSendQuota.
    """
    settings = await repo.get_email_settings()

    if not settings.provider_api_key and settings.provider != "ses":
        return {"success": False, "error": "No API key configured"}

    if settings.provider == "resend":
        from flydesk.email.adapters.resend_adapter import ResendEmailAdapter

        adapter = ResendEmailAdapter(api_key=settings.provider_api_key)
        result = await adapter.validate()
        return {
            "success": result.success,
            "error": result.error,
            "details": result.metadata,
        }
    elif settings.provider == "ses":
        return {"success": False, "error": "SES validation not yet implemented"}
    else:
        return {"success": False, "error": f"Unknown provider: {settings.provider}"}


# ---------------------------------------------------------------------------
# Validate credentials (wizard flow — validates without saving)
# ---------------------------------------------------------------------------


class ValidateCredentialsRequest(BaseModel):
    provider: str
    api_key: str = ""
    region: str = ""


@router.post("/validate-credentials", dependencies=[AdminSettings])
async def validate_credentials(body: ValidateCredentialsRequest) -> dict:
    """Validate email provider credentials inline without persisting.

    Used by the setup wizard to let admins verify their API key before
    committing to a full save.
    """
    if body.provider == "resend":
        if not body.api_key:
            return {"success": False, "error": "API key is required for Resend"}

        from flydesk.email.adapters.resend_adapter import ResendEmailAdapter

        adapter = ResendEmailAdapter(api_key=body.api_key)
        result = await adapter.validate()
        return {
            "success": result.success,
            "error": result.error,
            "details": result.metadata,
        }
    elif body.provider == "sendgrid":
        if not body.api_key:
            return {"success": False, "error": "API key is required for SendGrid"}
        return {"success": True, "error": None, "details": {"provider": "sendgrid"}}
    elif body.provider == "ses":
        if not body.region:
            return {"success": False, "error": "AWS region is required for SES"}
        return {"success": True, "error": None, "details": {"provider": "ses", "region": body.region}}
    else:
        return {"success": False, "error": f"Unknown provider: {body.provider}"}


# ---------------------------------------------------------------------------
# Email-enabled users & identity check
# ---------------------------------------------------------------------------


@router.get("/users", dependencies=[AdminSettings])
async def list_email_users(sf: SessionFactory) -> dict:
    """List local users who have an email address configured.

    Returns a list of users that the identity resolver can match
    when an inbound email arrives.
    """
    from flydesk.models.local_user import LocalUserRow

    async with sf() as session:
        stmt = (
            select(
                LocalUserRow.id,
                LocalUserRow.username,
                LocalUserRow.email,
                LocalUserRow.display_name,
                LocalUserRow.is_active,
            )
            .where(LocalUserRow.email != "")
            .where(LocalUserRow.email.isnot(None))
            .order_by(LocalUserRow.display_name)
        )
        rows = (await session.execute(stmt)).all()

    return {
        "users": [
            {
                "id": r.id,
                "username": r.username,
                "email": r.email,
                "display_name": r.display_name,
                "is_active": r.is_active,
            }
            for r in rows
        ]
    }


class IdentityCheckRequest(BaseModel):
    email: str


@router.post("/check-identity", dependencies=[AdminSettings])
async def check_identity(body: IdentityCheckRequest, sf: SessionFactory) -> dict:
    """Check whether an email address resolves to a known user.

    Useful for verifying that inbound emails from a given address
    will be accepted and correctly associated with a user account.
    """
    from flydesk.email.identity import EmailIdentityResolver

    resolver = EmailIdentityResolver(sf)
    identity = await resolver.resolve(body.email.strip())

    if identity is None:
        return {
            "resolved": False,
            "message": f"No user found for '{body.email}'. Inbound emails from this address will be rejected.",
        }

    return {
        "resolved": True,
        "user_id": identity.user_id,
        "display_name": identity.display_name,
        "email": identity.email,
        "message": f"Resolves to user '{identity.display_name or identity.user_id}'.",
    }


# ---------------------------------------------------------------------------
# Simulate inbound email (dev mode)
# ---------------------------------------------------------------------------


class SimulateInboundRequest(BaseModel):
    from_address: str
    subject: str = "Test inbound email"
    body: str = "This is a simulated inbound email for testing the pipeline."


@router.post("/simulate-inbound", dependencies=[AdminSettings])
async def simulate_inbound(
    body: SimulateInboundRequest,
    repo: SettingsRepo,
    sf: SessionFactory,
) -> dict:
    """Simulate an inbound email through the full pipeline.

    Runs: parse → identity resolution → thread creation → auto-reply.
    Does NOT require external webhooks or ngrok — works entirely locally.
    """
    import uuid

    from flydesk.email.identity import EmailIdentityResolver
    from flydesk.email.threading import EmailThreadTracker

    settings = await repo.get_email_settings()

    # Step 1: Resolve sender identity
    resolver = EmailIdentityResolver(sf)
    identity = await resolver.resolve(body.from_address.strip())

    if identity is None:
        return {
            "success": False,
            "step_reached": "identity",
            "error": f"Unknown sender: '{body.from_address}'. Add a user with this email first.",
        }

    # Step 2: Create/resolve thread
    tracker = EmailThreadTracker(sf)
    fake_message_id = f"<sim-{uuid.uuid4().hex[:12]}@flydesk.local>"
    conversation_id, is_new = await tracker.resolve_conversation(
        message_id=fake_message_id,
        in_reply_to=None,
        references=[],
        subject=body.subject,
        participants=[
            {"email": body.from_address, "role": "sender"},
            {"email": settings.from_address, "role": "recipient"},
        ],
    )

    result: dict = {
        "success": True,
        "identity": {
            "user_id": identity.user_id,
            "display_name": identity.display_name,
            "email": identity.email,
        },
        "thread": {
            "conversation_id": conversation_id,
            "is_new": is_new,
            "message_id": fake_message_id,
        },
        "auto_reply_enabled": settings.auto_reply,
    }

    # Step 3: Send auto-reply if enabled and email is configured
    if settings.auto_reply and settings.enabled and settings.provider_api_key:
        try:
            if settings.provider == "resend":
                from flydesk.email.adapters.resend_adapter import ResendEmailAdapter

                email_port = ResendEmailAdapter(api_key=settings.provider_api_key)
            else:
                result["reply_sent"] = False
                result["reply_note"] = f"Provider '{settings.provider}' not supported for simulation"
                return result

            from flydesk.email.formatter import EmailFormatter
            from flydesk.email.models import OutboundEmail

            formatter = EmailFormatter()
            reply_text = (
                "Thank you for your email. We have received your message "
                "and will get back to you shortly."
            )

            signature_html = settings.signature_html
            if not signature_html:
                from flydesk.email.signature import build_default_signature

                signature_html = build_default_signature(
                    agent_name=settings.from_display_name or "Ember",
                    from_address=settings.from_address,
                    logo_url=_logo_url_for(settings),
                )

            html_body = formatter.format_response(reply_text, signature_html=signature_html)

            email = OutboundEmail(
                from_address=settings.from_address,
                from_name=settings.from_display_name or "Ember",
                to=[body.from_address],
                subject=f"Re: {body.subject}",
                html_body=html_body,
                text_body=reply_text,
                in_reply_to=fake_message_id,
                references=[fake_message_id],
            )

            send_result = await email_port.send(email)
            result["reply_sent"] = send_result.success
            if send_result.success:
                result["reply_message_id"] = send_result.provider_message_id
                # Record outbound for threading
                await tracker.record_outbound(conversation_id, send_result.provider_message_id or "")
            else:
                result["reply_error"] = send_result.error
        except Exception as exc:
            logger.exception("Failed to send simulated reply")
            result["reply_sent"] = False
            result["reply_error"] = str(exc)
    else:
        result["reply_sent"] = False
        reasons = []
        if not settings.auto_reply:
            reasons.append("auto-reply is disabled")
        if not settings.enabled:
            reasons.append("email is not enabled")
        if not settings.provider_api_key:
            reasons.append("no API key configured")
        result["reply_note"] = f"Reply not sent: {', '.join(reasons)}"

    return result


# ---------------------------------------------------------------------------
# Signature image upload / serve
# ---------------------------------------------------------------------------

_ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
_MAX_IMAGE_SIZE = 2 * 1024 * 1024  # 2 MB


@router.post("/signature-image", dependencies=[AdminSettings])
async def upload_signature_image(
    file: UploadFile,
    repo: SettingsRepo,
) -> dict:
    """Upload a logo or image and store as a base64 data URI for portability."""
    if file.content_type not in _ALLOWED_IMAGE_TYPES:
        return {"success": False, "error": "Only PNG, JPEG, GIF, and WebP images are allowed."}

    contents = await file.read()
    if len(contents) > _MAX_IMAGE_SIZE:
        return {"success": False, "error": "Image must be under 2 MB."}

    b64 = base64.b64encode(contents).decode()
    data_uri = f"data:{file.content_type};base64,{b64}"

    # Persist the data URI in email settings
    settings = await repo.get_email_settings()
    updated = settings.model_copy(update={"signature_image_url": data_uri})
    await repo.set_email_settings(updated)

    return {"success": True, "url": data_uri}


@router.delete("/signature-image", dependencies=[AdminSettings])
async def delete_signature_image(repo: SettingsRepo) -> dict:
    """Remove the custom signature image and revert to the default logo."""
    settings = await repo.get_email_settings()
    updated = settings.model_copy(update={"signature_image_url": ""})
    await repo.set_email_settings(updated)
    return {"success": True}


# ---------------------------------------------------------------------------
# Disconnect (reset provider credentials)
# ---------------------------------------------------------------------------


@router.post("/disconnect", dependencies=[AdminSettings])
async def disconnect_email(repo: SettingsRepo) -> dict:
    """Clear provider credentials and disable email channel."""
    settings = await repo.get_email_settings()
    updated = settings.model_copy(update={
        "provider_api_key": "",
        "enabled": False,
    })
    await repo.set_email_settings(updated)
    return {"success": True, "message": "Email channel disconnected."}
