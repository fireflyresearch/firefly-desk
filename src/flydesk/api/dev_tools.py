# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Dev tools API: webhook log viewer, tunnel management, pyngrok setup."""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from flydesk.api.deps import get_settings_repo
from flydesk.config import get_config
from flydesk.rbac.guards import AdminSettings
from flydesk.settings.repository import SettingsRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dev-tools", tags=["dev-tools"])

SettingsRepo = Annotated[SettingsRepository, Depends(get_settings_repo)]


# ---------------------------------------------------------------------------
# Webhook log (proxied from email_inbound's WebhookLog)
# ---------------------------------------------------------------------------

def _get_webhook_log(request: Request):
    from flydesk.email.webhook_log import WebhookLog

    return getattr(request.app.state, "webhook_log", WebhookLog())


@router.get("/log", dependencies=[AdminSettings])
async def list_webhook_log(request: Request, limit: int = 50) -> dict:
    """Return recent webhook log entries (newest first)."""
    wl = _get_webhook_log(request)
    entries = wl.list(limit=limit)
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
async def get_webhook_log_entry(entry_id: str, request: Request) -> dict:
    """Return a single webhook log entry with full payload."""
    wl = _get_webhook_log(request)
    entry = wl.get(entry_id)
    if entry is None:
        return {"error": "Entry not found"}
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
async def clear_webhook_log(request: Request) -> dict:
    """Clear all webhook log entries."""
    wl = _get_webhook_log(request)
    wl.clear()
    return {"success": True}


# ---------------------------------------------------------------------------
# Tunnel management
# ---------------------------------------------------------------------------

def _get_tunnel_manager(request: Request):
    """Lazy-init a TunnelManager singleton on app.state."""
    from flydesk.email.tunnel import TunnelManager

    if not hasattr(request.app.state, "tunnel_manager"):
        request.app.state.tunnel_manager = TunnelManager()
    return request.app.state.tunnel_manager


@router.get("/tunnel/status", dependencies=[AdminSettings])
async def tunnel_status(request: Request) -> dict:
    """Return tunnel availability and active state."""
    config = get_config()
    if not config.dev_mode:
        return {"active": False, "available": False, "error": "Tunnel is only available in dev mode"}

    manager = _get_tunnel_manager(request)
    info = manager.status()
    return {"active": info.active, "url": info.url, "available": info.available, "error": info.error, "backend": info.backend}


@router.post("/tunnel/start", dependencies=[AdminSettings])
async def tunnel_start(request: Request, repo: SettingsRepo) -> dict:
    """Start a dev tunnel (ngrok or cloudflared)."""
    config = get_config()
    if not config.dev_mode:
        return {"active": False, "available": False, "error": "Tunnel is only available in dev mode"}

    settings = await repo.get_email_settings()
    auth_token = settings.ngrok_auth_token or None
    backend = settings.tunnel_backend or "ngrok"

    manager = _get_tunnel_manager(request)
    info = await asyncio.to_thread(manager.start, 8000, auth_token, backend)
    return {"active": info.active, "url": info.url, "available": info.available, "error": info.error, "backend": info.backend}


@router.post("/tunnel/stop", dependencies=[AdminSettings])
async def tunnel_stop(request: Request) -> dict:
    """Stop the active dev tunnel."""
    config = get_config()
    if not config.dev_mode:
        return {"active": False, "available": False, "error": "Tunnel is only available in dev mode"}

    manager = _get_tunnel_manager(request)
    info = await asyncio.to_thread(manager.stop)
    return {"active": info.active, "url": info.url, "available": info.available, "error": info.error, "backend": info.backend}


# ---------------------------------------------------------------------------
# Backend discovery
# ---------------------------------------------------------------------------

@router.get("/tunnel/backends", dependencies=[AdminSettings])
async def tunnel_backends(request: Request) -> dict:
    """Return which tunnel backends are available."""
    manager = _get_tunnel_manager(request)
    return {
        "backends": [
            {"id": "ngrok", "label": "ngrok", "available": manager.available, "requires_auth": True},
            {"id": "cloudflared", "label": "Cloudflare Tunnel", "available": manager.cloudflared_available, "requires_auth": False},
        ]
    }


# ---------------------------------------------------------------------------
# pyngrok management
# ---------------------------------------------------------------------------

@router.get("/tunnel/pyngrok-status", dependencies=[AdminSettings])
async def pyngrok_status() -> dict:
    """Check if pyngrok is installed and importable."""
    try:
        import pyngrok
        return {"installed": True, "version": pyngrok.__version__}
    except ImportError:
        return {"installed": False, "version": None}


@router.post("/tunnel/install-pyngrok", dependencies=[AdminSettings])
async def install_pyngrok() -> dict:
    """Install pyngrok via pip in the running environment."""
    import subprocess
    import sys

    try:
        result = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, "-m", "pip", "install", "pyngrok"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            return {"success": True, "message": "pyngrok installed successfully"}
        return {"success": False, "error": result.stderr}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Integrations discovery
# ---------------------------------------------------------------------------

@router.get("/integrations", dependencies=[AdminSettings])
async def list_integrations(repo: SettingsRepo) -> dict:
    """Return active integrations and their webhook paths."""
    settings = await repo.get_email_settings()
    integrations = []
    if settings.enabled and settings.provider:
        integrations.append({
            "type": "email",
            "provider": settings.provider,
            "enabled": True,
            "webhook_path": f"/api/email/inbound/{settings.provider}",
        })
    return {"integrations": integrations}


# ---------------------------------------------------------------------------
# Auth token management
# ---------------------------------------------------------------------------

class AuthTokenRequest(BaseModel):
    auth_token: str


@router.put("/tunnel/auth-token", dependencies=[AdminSettings])
async def save_tunnel_auth_token(body: AuthTokenRequest, repo: SettingsRepo) -> dict:
    """Save ngrok auth token to settings."""
    settings = await repo.get_email_settings()
    updated = settings.model_copy(update={"ngrok_auth_token": body.auth_token})
    await repo.set_email_settings(updated)
    return {"success": True}
