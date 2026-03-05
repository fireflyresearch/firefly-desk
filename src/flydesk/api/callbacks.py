# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Admin API for managing outbound callback (webhook) configurations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from flydesk.api.deps import get_settings_repo
from flydesk.rbac.guards import AdminSettings
from flydesk.settings.repository import SettingsRepository

router = APIRouter(prefix="/api/callbacks", tags=["callbacks"])

SettingsRepo = Annotated[SettingsRepository, Depends(get_settings_repo)]


def _validate_callback_url(url: str) -> str:
    """Validate callback URL: must be http(s), reject private/reserved IPs."""
    from urllib.parse import urlparse
    import ipaddress

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Callback URL must use http or https scheme")
    hostname = parsed.hostname or ""
    if not hostname:
        raise ValueError("Callback URL has no hostname")
    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            raise ValueError(f"Callback URL targets a private/reserved address: {hostname}")
    except ValueError as exc:
        if "private" in str(exc) or "reserved" in str(exc) or "loopback" in str(exc):
            raise
    return url


class CreateCallbackRequest(BaseModel):
    url: str
    events: list[str] = []
    enabled: bool = True


class UpdateCallbackRequest(BaseModel):
    url: str | None = None
    events: list[str] | None = None
    enabled: bool | None = None


@router.get("", dependencies=[AdminSettings])
async def list_callbacks(repo: SettingsRepo) -> dict:
    """List all configured outbound callbacks."""
    callbacks = await repo.get_callbacks()
    return {"callbacks": callbacks}


@router.post("", dependencies=[AdminSettings])
async def create_callback(body: CreateCallbackRequest, repo: SettingsRepo) -> dict:
    """Add a new outbound callback endpoint."""
    try:
        _validate_callback_url(body.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    callbacks = await repo.get_callbacks()

    callback = {
        "id": str(uuid.uuid4()),
        "url": body.url,
        "secret": uuid.uuid4().hex,
        "events": body.events,
        "enabled": body.enabled,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    callbacks.append(callback)
    await repo.set_callbacks(callbacks)

    return callback


@router.put("/{callback_id}", dependencies=[AdminSettings])
async def update_callback(
    callback_id: str, body: UpdateCallbackRequest, repo: SettingsRepo
) -> dict:
    """Update an existing callback configuration."""
    callbacks = await repo.get_callbacks()

    for i, cb in enumerate(callbacks):
        if cb.get("id") == callback_id:
            if body.url is not None:
                try:
                    _validate_callback_url(body.url)
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc
                cb["url"] = body.url
            if body.events is not None:
                cb["events"] = body.events
            if body.enabled is not None:
                cb["enabled"] = body.enabled
            callbacks[i] = cb
            await repo.set_callbacks(callbacks)
            return cb

    raise HTTPException(status_code=404, detail="Callback not found")


@router.delete("/{callback_id}", dependencies=[AdminSettings])
async def delete_callback(callback_id: str, repo: SettingsRepo) -> dict:
    """Remove a callback configuration."""
    callbacks = await repo.get_callbacks()
    original_len = len(callbacks)
    callbacks = [cb for cb in callbacks if cb.get("id") != callback_id]

    if len(callbacks) == original_len:
        raise HTTPException(status_code=404, detail="Callback not found")

    await repo.set_callbacks(callbacks)
    return {"success": True}


@router.post("/{callback_id}/test", dependencies=[AdminSettings])
async def test_callback(callback_id: str, repo: SettingsRepo, request: Request) -> dict:
    """Send a test payload to a callback endpoint."""
    callbacks = await repo.get_callbacks()
    callback = None
    for cb in callbacks:
        if cb.get("id") == callback_id:
            callback = cb
            break

    if callback is None:
        raise HTTPException(status_code=404, detail="Callback not found")

    dispatcher = getattr(request.app.state, "callback_dispatcher", None)
    if dispatcher is None:
        raise HTTPException(status_code=503, detail="Callback dispatcher not available")

    # Send directly (not fire-and-forget) so we can report the result.
    import hashlib
    import hmac
    import json

    payload = {
        "event": "test",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {"message": "This is a test callback from Flydesk."},
    }
    body_str = json.dumps(payload, default=str)
    signature = hmac.new(
        callback.get("secret", "").encode(), body_str.encode(), hashlib.sha256
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Flydesk-Signature": signature,
        "X-Flydesk-Event": "test",
    }

    http_client = getattr(request.app.state, "http_client", None)
    if http_client is None:
        raise HTTPException(status_code=503, detail="HTTP client not available")

    try:
        resp = await http_client.post(
            callback["url"], content=body_str, headers=headers, timeout=5.0
        )
        return {
            "success": resp.status_code < 400,
            "status_code": resp.status_code,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@router.get("/delivery-log", dependencies=[AdminSettings])
async def list_delivery_log(
    request: Request,
    limit: int = 50,
    callback_id: str | None = None,
    event: str | None = None,
    status: str | None = None,
) -> dict:
    """Return recent callback delivery attempts."""
    delivery_repo = getattr(request.app.state, "callback_delivery_repo", None)
    if delivery_repo is None:
        return {"entries": []}
    entries = await delivery_repo.list(
        limit=limit, callback_id=callback_id, event=event, status=status,
    )
    return {"entries": entries}
