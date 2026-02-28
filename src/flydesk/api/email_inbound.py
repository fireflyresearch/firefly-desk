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
"""

from __future__ import annotations

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from flydesk.api.deps import get_email_channel_adapter, get_settings_repo
from flydesk.channels.models import AgentResponse
from flydesk.email.channel_adapter import EmailChannelAdapter
from flydesk.settings.repository import SettingsRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/email", tags=["email"])

SettingsRepo = Annotated[SettingsRepository, Depends(get_settings_repo)]
Adapter = Annotated[EmailChannelAdapter, Depends(get_email_channel_adapter)]

_SUPPORTED_PROVIDERS = ("resend", "ses")


@router.post("/inbound/{provider}")
async def receive_inbound_email(
    provider: str,
    request: Request,
    settings_repo: SettingsRepo,
    adapter: Adapter,
) -> dict:
    """Receive inbound email from provider webhook (Resend, SES, etc.).

    Pipeline:
    1. Validate provider name.
    2. Parse the JSON payload via the channel adapter.
    3. If the sender is unknown, return ``{"status": "skipped"}``.
    4. If ``auto_reply`` is disabled, return ``{"status": "stored"}``.
    5. Otherwise, generate an acknowledgment and send the reply.
    """
    # 1. Validate provider.
    if provider not in _SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=400, detail=f"Unknown email provider: {provider}"
        )

    # 2. Parse request body as JSON.
    body = await request.body()
    logger.info("Received inbound email via %s (%d bytes)", provider, len(body))

    try:
        body_json = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("Invalid JSON in inbound email payload: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    # 3. Parse through the adapter.
    message = await adapter.receive({"provider": provider, "payload": body_json})

    if message is None:
        logger.info("Inbound email from unknown sender -- skipping")
        return {"status": "skipped", "reason": "unknown_sender"}

    conversation_id = message.conversation_id

    # 4. Check auto_reply setting.
    email_settings = await settings_repo.get_email_settings()

    if not email_settings.auto_reply:
        logger.info(
            "auto_reply disabled -- storing message for conversation %s",
            conversation_id,
        )
        return {"status": "stored", "conversation_id": conversation_id}

    # 5. Generate and send an auto-reply.
    #
    # TODO: Replace this placeholder acknowledgment with a real DeskAgent
    # invocation once the agent's channel-aware pipeline is wired (Task 6+).
    agent_response = AgentResponse(
        content="Thank you for your email. We have received your message "
        "and will get back to you shortly.",
        metadata={"source": "auto_reply", "channel": "email"},
    )

    await adapter.send(conversation_id, agent_response)

    logger.info("Processed inbound email for conversation %s", conversation_id)
    return {"status": "processed", "conversation_id": conversation_id}
