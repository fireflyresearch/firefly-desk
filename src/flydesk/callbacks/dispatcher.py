# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Outbound callback dispatcher -- sends HMAC-signed webhooks to registered URLs."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import httpx

    from flydesk.callbacks.delivery_repository import CallbackDeliveryRepository
    from flydesk.settings.repository import SettingsRepository

logger = logging.getLogger(__name__)

_RETRY_DELAYS = [0, 30, 300]  # immediate, 30s, 5min


class CallbackDispatcher:
    """Dispatches outbound webhook callbacks to registered endpoints.

    Callbacks are sent as fire-and-forget ``asyncio`` tasks so they
    never block the caller.  Each request is signed with HMAC-SHA256
    using the callback's configured secret.
    """

    def __init__(
        self,
        settings_repo: SettingsRepository,
        http_client: httpx.AsyncClient,
        delivery_repo: CallbackDeliveryRepository | None = None,
    ) -> None:
        self._settings_repo = settings_repo
        self._http_client = http_client
        self._delivery_repo = delivery_repo

    async def dispatch(self, event: str, data: dict[str, Any]) -> None:
        """Send *event* with *data* to all matching callbacks (fire-and-forget)."""
        try:
            settings = await self._settings_repo.get_email_settings()
        except Exception:
            logger.warning("Failed to load settings for callback dispatch", exc_info=True)
            return

        callbacks = settings.outbound_callbacks or []

        for cb in callbacks:
            if not cb.get("enabled", True):
                continue
            cb_events = cb.get("events", [])
            if cb_events and event not in cb_events:
                continue

            url = cb.get("url", "")
            secret = cb.get("secret", "")
            if not url:
                continue

            callback_id = cb.get("id", "")
            asyncio.create_task(
                self._deliver_with_retries(callback_id, url, secret, event, data)
            )

    async def _deliver_with_retries(
        self,
        callback_id: str,
        url: str,
        secret: str,
        event: str,
        data: dict[str, Any],
    ) -> None:
        """POST a signed payload to a callback URL with exponential backoff retries."""
        payload = {
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        body = json.dumps(payload, default=str)

        # Compute HMAC-SHA256 signature.
        signature = hmac.new(
            secret.encode(), body.encode(), hashlib.sha256
        ).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-Flydesk-Signature": signature,
            "X-Flydesk-Event": event,
        }

        for attempt, delay in enumerate(_RETRY_DELAYS, start=1):
            if delay > 0:
                await asyncio.sleep(delay)
            try:
                resp = await self._http_client.post(
                    url, content=body, headers=headers, timeout=5.0
                )
                if self._delivery_repo:
                    await self._delivery_repo.record(
                        callback_id=callback_id,
                        event=event,
                        url=url,
                        attempt=attempt,
                        status="success",
                        status_code=resp.status_code,
                        payload=payload,
                    )
                logger.info(
                    "Callback %s -> %s (attempt %d, %d)",
                    event, url, attempt, resp.status_code,
                )
                return  # Success — stop retrying
            except Exception as exc:
                logger.warning(
                    "Callback attempt %d failed: %s -> %s: %s",
                    attempt, event, url, exc,
                )
                if self._delivery_repo:
                    await self._delivery_repo.record(
                        callback_id=callback_id,
                        event=event,
                        url=url,
                        attempt=attempt,
                        status="failed",
                        error=str(exc),
                        payload=payload,
                    )

        logger.error("Callback delivery exhausted: %s -> %s", event, url)
