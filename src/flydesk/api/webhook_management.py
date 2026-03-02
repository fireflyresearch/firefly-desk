# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Webhook management API: inbound webhook endpoint discovery and log viewer."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from flydesk.api.deps import get_settings_repo, get_webhook_log_repo
from flydesk.email.webhook_log_repository import WebhookLogRepository
from flydesk.rbac.guards import AdminSettings
from flydesk.settings.repository import SettingsRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhook-admin", tags=["webhook-admin"])

SettingsRepo = Annotated[SettingsRepository, Depends(get_settings_repo)]
LogRepo = Annotated[WebhookLogRepository, Depends(get_webhook_log_repo)]


# ---------------------------------------------------------------------------
# Inbound webhook endpoint discovery
# ---------------------------------------------------------------------------


@router.get("/endpoints", dependencies=[AdminSettings])
async def list_webhook_endpoints(repo: SettingsRepo) -> dict:
    """List configured inbound webhook endpoints per email provider.

    Shows endpoints whenever a provider is configured (has credentials),
    regardless of whether the email channel is enabled.
    """
    settings = await repo.get_email_settings()
    endpoints = []
    has_credentials = bool(settings.provider_api_key or settings.provider_region)
    if has_credentials and settings.provider:
        provider = settings.provider.lower()
        endpoints.append({
            "provider": provider,
            "webhook_path": f"/api/email/inbound/{provider}",
            "signature_verification": provider in ("resend", "sendgrid"),
            "enabled": settings.enabled,
        })
    return {"endpoints": endpoints, "email_enabled": settings.enabled}


# ---------------------------------------------------------------------------
# Webhook log (DB-backed)
# ---------------------------------------------------------------------------


@router.get("/log", dependencies=[AdminSettings])
async def list_webhook_log(log_repo: LogRepo, limit: int = 50) -> dict:
    """Return recent webhook log entries (newest first)."""
    entries = await log_repo.list(limit=limit)
    return {
        "entries": [
            {
                "id": e.id,
                "timestamp": e.timestamp.isoformat(),
                "provider": e.provider,
                "status": e.status,
                "from_address": e.from_address,
                "subject": e.subject,
                "processing_time_ms": e.processing_time_ms,
                "error": e.error,
            }
            for e in entries
        ]
    }


@router.get("/log/{entry_id}", dependencies=[AdminSettings])
async def get_webhook_log_entry(entry_id: str, log_repo: LogRepo) -> dict:
    """Return a single webhook log entry with full payload."""
    entry = await log_repo.get(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {
        "id": entry.id,
        "timestamp": entry.timestamp.isoformat(),
        "provider": entry.provider,
        "status": entry.status,
        "from_address": entry.from_address,
        "subject": entry.subject,
        "processing_time_ms": entry.processing_time_ms,
        "error": entry.error,
        "payload_preview": entry.payload_preview,
    }


@router.delete("/log", dependencies=[AdminSettings])
async def clear_webhook_log(log_repo: LogRepo) -> dict:
    """Clear all webhook log entries."""
    await log_repo.clear()
    return {"success": True}
