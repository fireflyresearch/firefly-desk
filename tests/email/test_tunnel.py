# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Unit tests for TunnelManager with mocked pyngrok."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from flydesk.email.tunnel import TunnelInfo, TunnelManager


def _make_pyngrok_mocks(ngrok_mock: MagicMock | None = None):
    """Create a pyngrok module mock with its ngrok sub-module wired up."""
    mock_ngrok = ngrok_mock or MagicMock()
    mock_pyngrok = MagicMock()
    mock_pyngrok.ngrok = mock_ngrok
    return mock_pyngrok, mock_ngrok


class TestTunnelAvailability:
    def test_available_when_pyngrok_installed(self):
        manager = TunnelManager()
        with patch.dict("sys.modules", {"pyngrok": MagicMock()}):
            assert manager.available is True

    def test_unavailable_when_pyngrok_missing(self):
        manager = TunnelManager()
        with patch.dict("sys.modules", {"pyngrok": None}):
            assert manager.available is False


class TestTunnelStatus:
    def test_status_initially_inactive(self):
        manager = TunnelManager()
        info = manager.status()
        assert info.active is False
        assert info.url is None
        assert info.error is None


class TestTunnelStart:
    def test_start_creates_tunnel(self):
        manager = TunnelManager()
        mock_tunnel = MagicMock()
        mock_tunnel.public_url = "https://abc123.ngrok.io"

        mock_ngrok = MagicMock()
        mock_ngrok.connect.return_value = mock_tunnel
        mock_pyngrok, _ = _make_pyngrok_mocks(mock_ngrok)

        with (
            patch.dict("sys.modules", {"pyngrok": mock_pyngrok, "pyngrok.ngrok": mock_ngrok}),
            patch.object(TunnelManager, "available", new_callable=lambda: property(lambda self: True)),
        ):
            info = manager.start(8000)

        assert info.active is True
        assert info.url == "https://abc123.ngrok.io"
        assert info.error is None

    def test_start_upgrades_http_to_https(self):
        manager = TunnelManager()
        mock_tunnel = MagicMock()
        mock_tunnel.public_url = "http://abc123.ngrok.io"

        mock_ngrok = MagicMock()
        mock_ngrok.connect.return_value = mock_tunnel
        mock_pyngrok, _ = _make_pyngrok_mocks(mock_ngrok)

        with (
            patch.dict("sys.modules", {"pyngrok": mock_pyngrok, "pyngrok.ngrok": mock_ngrok}),
            patch.object(TunnelManager, "available", new_callable=lambda: property(lambda self: True)),
        ):
            info = manager.start(8000)

        assert info.url == "https://abc123.ngrok.io"

    def test_start_idempotent(self):
        manager = TunnelManager()
        manager._tunnel = MagicMock()
        manager._url = "https://existing.ngrok.io"

        info = manager.start(8000)
        assert info.active is True
        assert info.url == "https://existing.ngrok.io"

    def test_start_returns_error_when_unavailable(self):
        manager = TunnelManager()
        with patch.dict("sys.modules", {"pyngrok": None}):
            info = manager.start(8000)

        assert info.active is False
        assert info.available is False
        assert "not installed" in (info.error or "")

    def test_start_auth_error(self):
        manager = TunnelManager()
        mock_ngrok = MagicMock()
        mock_ngrok.connect.side_effect = Exception("auth token not found")
        mock_pyngrok, _ = _make_pyngrok_mocks(mock_ngrok)

        with (
            patch.dict("sys.modules", {"pyngrok": mock_pyngrok, "pyngrok.ngrok": mock_ngrok}),
            patch.object(TunnelManager, "available", new_callable=lambda: property(lambda self: True)),
        ):
            info = manager.start(8000)

        assert info.active is False
        assert "auth token" in (info.error or "").lower()

    def test_start_binary_not_found(self):
        manager = TunnelManager()
        mock_ngrok = MagicMock()
        mock_ngrok.connect.side_effect = Exception("ngrok not found")
        mock_pyngrok, _ = _make_pyngrok_mocks(mock_ngrok)

        with (
            patch.dict("sys.modules", {"pyngrok": mock_pyngrok, "pyngrok.ngrok": mock_ngrok}),
            patch.object(TunnelManager, "available", new_callable=lambda: property(lambda self: True)),
        ):
            info = manager.start(8000)

        assert info.active is False
        assert "not found" in (info.error or "").lower()


class TestTunnelStop:
    def test_stop_noop_when_inactive(self):
        manager = TunnelManager()
        info = manager.stop()
        assert info.active is False
        assert info.error is None

    def test_stop_disconnects_tunnel(self):
        manager = TunnelManager()
        manager._tunnel = MagicMock()
        manager._url = "https://abc123.ngrok.io"

        mock_ngrok = MagicMock()
        mock_pyngrok, _ = _make_pyngrok_mocks(mock_ngrok)

        with patch.dict("sys.modules", {"pyngrok": mock_pyngrok, "pyngrok.ngrok": mock_ngrok}):
            info = manager.stop()

        assert info.active is False
        assert manager._tunnel is None
        assert manager._url is None
        mock_ngrok.disconnect.assert_called_once_with("https://abc123.ngrok.io")

    def test_stop_handles_disconnect_error(self):
        manager = TunnelManager()
        manager._tunnel = MagicMock()
        manager._url = "https://abc123.ngrok.io"

        mock_ngrok = MagicMock()
        mock_ngrok.disconnect.side_effect = Exception("already closed")
        mock_pyngrok, _ = _make_pyngrok_mocks(mock_ngrok)

        with patch.dict("sys.modules", {"pyngrok": mock_pyngrok, "pyngrok.ngrok": mock_ngrok}):
            info = manager.stop()

        # Should still clear state despite error
        assert info.active is False
        assert manager._tunnel is None


class TestTunnelInfoDefaults:
    def test_default_values(self):
        info = TunnelInfo()
        assert info.active is False
        assert info.url is None
        assert info.available is False
        assert info.error is None
