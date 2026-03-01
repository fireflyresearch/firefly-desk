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
    backend: str | None = None


class TunnelManager:
    """Wraps ``pyngrok`` to expose a local port via an ngrok HTTPS tunnel.

    All operations are idempotent:
    - ``start()`` when already active returns the existing URL.
    - ``stop()`` when inactive is a no-op.
    """

    def __init__(self) -> None:
        self._tunnel: object | None = None  # pyngrok NgrokTunnel or subprocess.Popen
        self._url: str | None = None
        self._active_backend: str | None = None

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

    @property
    def cloudflared_available(self) -> bool:
        """Return ``True`` if cloudflared binary is on PATH."""
        import shutil

        return shutil.which("cloudflared") is not None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def status(self) -> TunnelInfo:
        """Return current tunnel state without side-effects."""
        return TunnelInfo(
            active=self._tunnel is not None,
            url=self._url,
            available=self.available,
            backend=self._active_backend,
        )

    def start(
        self,
        port: int = 8000,
        auth_token: str | None = None,
        backend: str = "ngrok",
    ) -> TunnelInfo:
        """Start a tunnel (ngrok or cloudflared)."""
        if self._tunnel is not None:
            return TunnelInfo(
                active=True, url=self._url, available=True, backend=self._active_backend
            )

        if backend == "cloudflared":
            return self._start_cloudflared(port)

        return self._start_ngrok(port, auth_token)

    def stop(self) -> TunnelInfo:
        """Stop the active tunnel (no-op if inactive)."""
        if self._tunnel is None:
            return TunnelInfo(available=self.available)

        if self._active_backend == "cloudflared":
            self._stop_cloudflared()
        else:
            self._stop_ngrok()

        self._tunnel = None
        self._url = None
        self._active_backend = None
        return TunnelInfo(available=self.available)

    # ------------------------------------------------------------------
    # ngrok
    # ------------------------------------------------------------------

    def _start_ngrok(self, port: int, auth_token: str | None = None) -> TunnelInfo:
        if not self.available:
            return TunnelInfo(
                available=False,
                error="pyngrok is not installed. Install with: pip install 'flydesk[tunnel]'",
            )

        try:
            from pyngrok import conf as ngrok_conf
            from pyngrok import ngrok

            if auth_token:
                ngrok_conf.get_default().auth_token = auth_token

            tunnel = ngrok.connect(port, "http")
            url = tunnel.public_url

            if url.startswith("http://"):
                url = url.replace("http://", "https://", 1)

            self._tunnel = tunnel
            self._url = url
            self._active_backend = "ngrok"

            logger.info("ngrok tunnel started: %s -> localhost:%d", url, port)
            return TunnelInfo(active=True, url=url, available=True, backend="ngrok")

        except Exception as exc:
            msg = str(exc)
            if "auth" in msg.lower() or "token" in msg.lower():
                error = "ngrok auth token not set. Get one free at ngrok.com"
            elif "not found" in msg.lower() or "no such file" in msg.lower():
                error = "ngrok binary not found. Install from https://ngrok.com/download"
            else:
                error = f"Failed to start tunnel: {msg}"

            logger.warning("Tunnel start failed: %s", error)
            return TunnelInfo(available=True, error=error, backend="ngrok")

    def _stop_ngrok(self) -> None:
        try:
            from pyngrok import ngrok

            ngrok.disconnect(self._url)
            logger.info("ngrok tunnel stopped: %s", self._url)
        except Exception as exc:
            logger.warning("Error disconnecting ngrok: %s", exc)

    # ------------------------------------------------------------------
    # cloudflared
    # ------------------------------------------------------------------

    def _start_cloudflared(self, port: int) -> TunnelInfo:
        if not self.cloudflared_available:
            return TunnelInfo(
                available=False,
                error="cloudflared not found on PATH. Install from https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/",
            )

        try:
            import subprocess

            proc = subprocess.Popen(
                ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # cloudflared prints the URL to stderr; read lines until we find it
            import re

            url = None
            for _ in range(30):
                line = proc.stderr.readline()
                match = re.search(r"(https://[^\s]+\.trycloudflare\.com)", line)
                if match:
                    url = match.group(1)
                    break

            if url is None:
                proc.terminate()
                return TunnelInfo(
                    available=True,
                    error="Timed out waiting for cloudflared URL",
                    backend="cloudflared",
                )

            self._tunnel = proc
            self._url = url
            self._active_backend = "cloudflared"

            logger.info("cloudflared tunnel started: %s -> localhost:%d", url, port)
            return TunnelInfo(active=True, url=url, available=True, backend="cloudflared")

        except Exception as exc:
            logger.warning("cloudflared start failed: %s", exc)
            return TunnelInfo(
                available=True,
                error=f"Failed to start cloudflared: {exc}",
                backend="cloudflared",
            )

    def _stop_cloudflared(self) -> None:
        try:
            if hasattr(self._tunnel, "terminate"):
                self._tunnel.terminate()
                self._tunnel.wait(timeout=5)
            logger.info("cloudflared tunnel stopped: %s", self._url)
        except Exception as exc:
            logger.warning("Error stopping cloudflared: %s", exc)
