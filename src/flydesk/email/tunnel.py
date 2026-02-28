# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Built-in ngrok tunnel for dev-mode inbound email testing."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TunnelInfo:
    """Snapshot of tunnel state returned by every TunnelManager method."""

    active: bool = False
    url: str | None = None
    available: bool = False
    error: str | None = None


class TunnelManager:
    """Wraps ``pyngrok`` to expose a local port via an ngrok HTTPS tunnel.

    All operations are idempotent:
    - ``start()`` when already active returns the existing URL.
    - ``stop()`` when inactive is a no-op.
    """

    def __init__(self) -> None:
        self._tunnel: object | None = None  # pyngrok NgrokTunnel instance
        self._url: str | None = None

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """Return ``True`` if pyngrok is importable."""
        try:
            import pyngrok  # noqa: F401

            return True
        except ImportError:
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def status(self) -> TunnelInfo:
        """Return current tunnel state without side-effects."""
        return TunnelInfo(
            active=self._tunnel is not None,
            url=self._url,
            available=self.available,
        )

    def start(self, port: int = 8000) -> TunnelInfo:
        """Start an ngrok tunnel (or return existing one)."""
        if self._tunnel is not None:
            return TunnelInfo(active=True, url=self._url, available=True)

        if not self.available:
            return TunnelInfo(
                available=False,
                error="pyngrok is not installed. Install with: pip install 'flydesk[tunnel]'",
            )

        try:
            from pyngrok import ngrok

            tunnel = ngrok.connect(port, "http")
            url = tunnel.public_url

            # Ensure HTTPS
            if url.startswith("http://"):
                url = url.replace("http://", "https://", 1)

            self._tunnel = tunnel
            self._url = url

            logger.info("ngrok tunnel started: %s -> localhost:%d", url, port)
            return TunnelInfo(active=True, url=url, available=True)

        except Exception as exc:
            msg = str(exc)
            if "auth" in msg.lower() or "token" in msg.lower():
                error = (
                    "ngrok auth token not set. Run: ngrok config add-authtoken <TOKEN>"
                )
            elif "not found" in msg.lower() or "no such file" in msg.lower():
                error = "ngrok binary not found. Install from https://ngrok.com/download"
            else:
                error = f"Failed to start tunnel: {msg}"

            logger.warning("Tunnel start failed: %s", error)
            return TunnelInfo(available=True, error=error)

    def stop(self) -> TunnelInfo:
        """Stop the active tunnel (no-op if inactive)."""
        if self._tunnel is None:
            return TunnelInfo(available=self.available)

        try:
            from pyngrok import ngrok

            ngrok.disconnect(self._url)
            logger.info("ngrok tunnel stopped: %s", self._url)
        except Exception as exc:
            logger.warning("Error disconnecting tunnel: %s", exc)

        self._tunnel = None
        self._url = None
        return TunnelInfo(available=self.available)
