# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Inbound email webhook receiver."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from flydesk.api.deps import get_settings_repo
from flydesk.settings.repository import SettingsRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/email", tags=["email"])

SettingsRepo = Annotated[SettingsRepository, Depends(get_settings_repo)]


@router.post("/inbound/{provider}")
async def receive_inbound_email(
    provider: str,
    request: Request,
    settings_repo: SettingsRepo,
) -> dict:
    """Receive inbound email from provider webhook (Resend, SES, etc.).

    This endpoint will be fully wired when the email channel adapter
    and DeskAgent channel awareness are implemented in later tasks.
    """
    # Validate provider
    if provider not in ("resend", "ses"):
        raise HTTPException(
            status_code=400, detail=f"Unknown email provider: {provider}"
        )

    body = await request.body()

    logger.info("Received inbound email via %s (%d bytes)", provider, len(body))

    # TODO: Phase 5 wiring — parse email, resolve identity, route to agent
    return {"status": "accepted", "provider": provider}
