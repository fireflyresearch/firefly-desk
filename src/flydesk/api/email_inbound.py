# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Inbound email webhook receiver.

Receives inbound emails from provider webhooks (Resend, SES, etc.),
parses them via the :class:`EmailChannelAdapter`, and optionally
invokes the agent to generate an auto-reply.

Also provides a webhook log API for debugging inbound email processing.
"""

from __future__ import annotations

import json
import logging
import time
import uuid as _uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from flydesk.api.deps import get_email_channel_adapter, get_settings_repo
from flydesk.auth.models import UserSession
from flydesk.channels.models import AgentResponse as ChannelAgentResponse
from flydesk.conversation.models import Conversation, Message, MessageRole
from flydesk.email.channel_adapter import EmailChannelAdapter
from flydesk.email.webhook_log import WebhookLog, WebhookLogEntry
from flydesk.rbac.guards import AdminSettings
from flydesk.settings.repository import SettingsRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/email", tags=["email"])

SettingsRepo = Annotated[SettingsRepository, Depends(get_settings_repo)]
Adapter = Annotated[EmailChannelAdapter, Depends(get_email_channel_adapter)]

_SUPPORTED_PROVIDERS = ("resend", "ses", "sendgrid")


def _get_webhook_log(request: Request) -> WebhookLog:
    """Retrieve the WebhookLog singleton from app state."""
    return getattr(request.app.state, "webhook_log", WebhookLog())


WebhookLogDep = Annotated[WebhookLog, Depends(_get_webhook_log)]


@router.post("/inbound/{provider}")
async def receive_inbound_email(
    provider: str,
    request: Request,
    settings_repo: SettingsRepo,
    adapter: Adapter,
    webhook_log: WebhookLogDep,
) -> dict:
    """Receive inbound email from provider webhook (Resend, SES, etc.).

    Pipeline:
    1. Validate provider name.
    2. Parse the JSON payload via the channel adapter.
    3. If the sender is unknown, return ``{"status": "skipped"}``.
    4. If ``auto_reply`` is disabled, return ``{"status": "stored"}``.
    5. Otherwise, generate an acknowledgment and send the reply.
    """
    start_time = time.monotonic()

    # 1. Validate provider.
    if provider not in _SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=400, detail=f"Unknown email provider: {provider}"
        )

    # 2. Parse request body — JSON (Resend/SES) or multipart/form-data (SendGrid).
    body = await request.body()
    logger.info("Received inbound email via %s (%d bytes)", provider, len(body))

    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        # SendGrid sends multipart/form-data.
        form = await request.form()
        body_json = {key: str(form[key]) for key in form}
        payload_preview = json.dumps(body_json, default=str)[:500]
    else:
        try:
            body_json = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning("Invalid JSON in inbound email payload: %s", exc)
            elapsed_ms = (time.monotonic() - start_time) * 1000
            webhook_log.record(WebhookLogEntry(
                provider=provider,
                status="error",
                payload_preview=body.decode(errors="replace")[:500],
                processing_time_ms=elapsed_ms,
                error=f"Invalid JSON: {exc}",
            ))
            raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    payload_preview = json.dumps(body_json, default=str)[:500]

    # Extract from/subject from common payload shapes for logging.
    from_addr = ""
    subject = ""
    payload_data = body_json
    if isinstance(payload_data, dict):
        from_addr = payload_data.get("from", "") or payload_data.get("sender", "") or ""
        subject = payload_data.get("subject", "") or ""
        # Resend wraps in "data"
        if "data" in payload_data and isinstance(payload_data["data"], dict):
            from_addr = from_addr or payload_data["data"].get("from", "") or ""
            subject = subject or payload_data["data"].get("subject", "") or ""

    # 2b. Verify webhook signature.
    is_valid = await adapter._email_port.verify_webhook_signature(
        headers=dict(request.headers),
        body=body,
    )
    if not is_valid:
        elapsed_ms = (time.monotonic() - start_time) * 1000
        webhook_log.record(WebhookLogEntry(
            provider=provider,
            status="rejected",
            from_address="",
            subject="",
            payload_preview=payload_preview,
            processing_time_ms=elapsed_ms,
            error="Invalid webhook signature",
        ))
        logger.warning("Rejected inbound email from %s: invalid signature", provider)
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # 3. Parse through the adapter.
    message = await adapter.receive({"provider": provider, "payload": body_json})

    if message is None:
        elapsed_ms = (time.monotonic() - start_time) * 1000
        webhook_log.record(WebhookLogEntry(
            provider=provider,
            status="skipped",
            from_address=from_addr,
            subject=subject,
            payload_preview=payload_preview,
            processing_time_ms=elapsed_ms,
        ))
        logger.info("Inbound email from unknown sender -- skipping")
        return {"status": "skipped", "reason": "unknown_sender"}

    conversation_id = message.conversation_id
    if conversation_id is None:
        logger.error("Adapter returned message with no conversation_id — skipping")
        elapsed_ms = (time.monotonic() - start_time) * 1000
        webhook_log.record(WebhookLogEntry(
            provider=provider,
            status="error",
            from_address=from_addr,
            subject=subject,
            payload_preview=payload_preview,
            processing_time_ms=elapsed_ms,
            error="No conversation_id",
        ))
        return {"status": "error", "reason": "no_conversation_id"}
    from_addr = from_addr or getattr(message, "user_id", "")

    # 4. Check auto_reply setting.
    email_settings = await settings_repo.get_email_settings()

    if not email_settings.auto_reply:
        elapsed_ms = (time.monotonic() - start_time) * 1000
        webhook_log.record(WebhookLogEntry(
            provider=provider,
            status="processed",
            from_address=from_addr,
            subject=subject,
            payload_preview=payload_preview,
            processing_time_ms=elapsed_ms,
        ))
        logger.info(
            "auto_reply disabled -- storing message for conversation %s",
            conversation_id,
        )
        return {"status": "stored", "conversation_id": conversation_id}

    # 5. Generate agent reply via DeskAgent
    desk_agent = getattr(request.app.state, "desk_agent", None)
    conversation_repo = getattr(request.app.state, "conversation_repo", None)

    if desk_agent is None or conversation_repo is None:
        logger.warning("DeskAgent or conversation_repo not available — skipping agent reply")
        elapsed_ms = (time.monotonic() - start_time) * 1000
        webhook_log.record(WebhookLogEntry(
            provider=provider,
            status="error",
            from_address=from_addr,
            subject=subject,
            payload_preview=payload_preview,
            processing_time_ms=elapsed_ms,
            error="Agent not configured",
        ))
        return {"status": "error", "reason": "agent_not_configured"}

    # Build a UserSession for the email sender
    user_session = UserSession(
        user_id=message.user_id,
        email=from_addr or message.user_id,
        display_name=message.metadata.get("from_name", message.user_id),
        roles=["user"],
        permissions=[],
        tenant_id="email",
        session_id=f"email-{conversation_id}",
        token_expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        raw_claims={},
    )

    # Ensure conversation exists with channel="email"
    conversation = await conversation_repo.get_conversation(
        message.conversation_id, message.user_id, include_deleted=False
    )
    is_new_conversation = conversation is None
    if is_new_conversation:
        conversation = Conversation(
            id=message.conversation_id,
            title=subject or "Email conversation",
            user_id=message.user_id,
            metadata={"channel": "email"},
            status="active",
        )
        await conversation_repo.create_conversation(conversation)

    # Persist inbound email as user message
    await conversation_repo.add_message(
        Message(
            id=str(_uuid.uuid4()),
            conversation_id=message.conversation_id,
            role=MessageRole.USER,
            content=message.content,
            metadata={"channel": "email", "subject": subject, "from_address": from_addr},
        ),
        user_id=message.user_id,
    )

    # Fetch callback_dispatcher once for use in both error and success paths
    callback_dispatcher = getattr(request.app.state, "callback_dispatcher", None)

    # Invoke the agent
    try:
        agent_result = await desk_agent.run(
            message=message.content,
            session=user_session,
            conversation_id=message.conversation_id,
            file_ids=message.metadata.get("file_ids"),
        )
        reply_content = agent_result.text
    except Exception as agent_exc:
        logger.error(
            "DeskAgent failed for email conversation %s: %s",
            conversation_id, agent_exc, exc_info=True,
        )
        # Dispatch agent.error callback
        if callback_dispatcher is not None:
            await callback_dispatcher.dispatch("agent.error", {
                "conversation_id": conversation_id,
                "error": str(agent_exc),
                "channel": "email",
            })
        elapsed_ms = (time.monotonic() - start_time) * 1000
        webhook_log.record(WebhookLogEntry(
            provider=provider,
            status="error",
            from_address=from_addr,
            subject=subject,
            payload_preview=payload_preview,
            processing_time_ms=elapsed_ms,
            error=f"Agent error: {agent_exc}",
        ))
        return {"status": "error", "reason": "agent_error"}

    # Persist agent reply as assistant message
    await conversation_repo.add_message(
        Message(
            id=str(_uuid.uuid4()),
            conversation_id=message.conversation_id,
            role=MessageRole.ASSISTANT,
            content=reply_content,
            metadata={"channel": "email", "turn_id": agent_result.turn_id},
        ),
        user_id=message.user_id,
    )

    # Send the reply via email adapter
    agent_response = ChannelAgentResponse(
        content=reply_content,
        metadata={"source": "agent", "channel": "email"},
    )

    try:
        await adapter.send(conversation_id, agent_response)
        status = "processed"
        error = None
    except Exception as exc:
        logger.error("Failed to send email reply: %s", exc, exc_info=True)
        status = "error"
        error = str(exc)

    elapsed_ms = (time.monotonic() - start_time) * 1000
    webhook_log.record(WebhookLogEntry(
        provider=provider,
        status=status,
        from_address=from_addr,
        subject=subject,
        payload_preview=payload_preview,
        processing_time_ms=elapsed_ms,
        error=error,
    ))

    # Dispatch callbacks
    if callback_dispatcher is not None:
        await callback_dispatcher.dispatch("email.received", {
            "from": from_addr,
            "subject": subject,
            "conversation_id": conversation_id,
            "status": status,
        })
        if is_new_conversation:
            await callback_dispatcher.dispatch("conversation.created", {
                "conversation_id": conversation_id,
                "channel": "email",
                "user_id": message.user_id,
                "subject": subject,
            })
        else:
            await callback_dispatcher.dispatch("conversation.updated", {
                "conversation_id": conversation_id,
                "channel": "email",
            })

    logger.info("Processed inbound email for conversation %s", conversation_id)
    return {"status": status, "conversation_id": conversation_id}


# ---------------------------------------------------------------------------
# Webhook log API
# ---------------------------------------------------------------------------


@router.get("/webhook-log", dependencies=[AdminSettings])
async def list_webhook_log(
    webhook_log: WebhookLogDep,
    limit: int = Query(default=50, ge=1, le=100),
) -> dict:
    """Return recent webhook log entries (newest first)."""
    entries = webhook_log.list(limit=limit)
    return {
        "entries": [
            {
                "id": e.id,
                "timestamp": e.timestamp.isoformat(),
                "provider": e.provider,
                "status": e.status,
                "from_address": e.from_address,
                "subject": e.subject,
                "processing_time_ms": round(e.processing_time_ms, 1),
                "error": e.error,
            }
            for e in entries
        ]
    }


@router.get("/webhook-log/{entry_id}", dependencies=[AdminSettings])
async def get_webhook_log_entry(entry_id: str, webhook_log: WebhookLogDep) -> dict:
    """Return a single webhook log entry with full payload."""
    entry = webhook_log.get(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Log entry not found")
    return {
        "id": entry.id,
        "timestamp": entry.timestamp.isoformat(),
        "provider": entry.provider,
        "status": entry.status,
        "from_address": entry.from_address,
        "subject": entry.subject,
        "payload_preview": entry.payload_preview,
        "processing_time_ms": round(entry.processing_time_ms, 1),
        "error": entry.error,
    }


@router.delete("/webhook-log", dependencies=[AdminSettings])
async def clear_webhook_log(webhook_log: WebhookLogDep) -> dict:
    """Clear all webhook log entries."""
    webhook_log.clear()
    return {"success": True}
