"""Tests for CallbackDispatcher retry logic."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from flydesk.callbacks.dispatcher import CallbackDispatcher


@pytest.fixture
def mock_settings_repo():
    repo = AsyncMock()
    repo.get_email_settings.return_value = MagicMock(
        outbound_callbacks=[
            {
                "id": "cb-1",
                "url": "https://example.com/hook",
                "secret": "test-secret",
                "events": ["email.received"],
                "enabled": True,
            }
        ]
    )
    return repo


@pytest.fixture
def mock_http_client():
    return AsyncMock()


@pytest.fixture
def mock_delivery_repo():
    return AsyncMock()


@pytest.fixture
def dispatcher(mock_settings_repo, mock_http_client, mock_delivery_repo):
    return CallbackDispatcher(
        settings_repo=mock_settings_repo,
        http_client=mock_http_client,
        delivery_repo=mock_delivery_repo,
    )


class TestDeliverWithRetries:
    async def test_succeeds_on_first_attempt(self, dispatcher, mock_http_client, mock_delivery_repo):
        """Successful first attempt: 1 POST, 1 delivery log with status=success."""
        mock_http_client.post.return_value = MagicMock(status_code=200)

        await dispatcher._deliver_with_retries(
            "cb-1", "https://example.com/hook", "secret", "email.received", {"key": "value"}
        )

        assert mock_http_client.post.call_count == 1
        mock_delivery_repo.record.assert_called_once()
        call_kwargs = mock_delivery_repo.record.call_args[1]
        assert call_kwargs["status"] == "success"
        assert call_kwargs["attempt"] == 1

    async def test_retries_on_failure_then_succeeds(self, dispatcher, mock_http_client, mock_delivery_repo):
        """First attempt fails, second succeeds: 2 POSTs, 2 delivery logs."""
        mock_http_client.post.side_effect = [
            Exception("Connection refused"),
            MagicMock(status_code=200),
        ]

        # Patch asyncio.sleep to avoid real delays
        with patch("flydesk.callbacks.dispatcher.asyncio.sleep", new_callable=AsyncMock):
            await dispatcher._deliver_with_retries(
                "cb-1", "https://example.com/hook", "secret", "email.received", {}
            )

        assert mock_http_client.post.call_count == 2
        assert mock_delivery_repo.record.call_count == 2

    async def test_exhausts_all_retries(self, dispatcher, mock_http_client, mock_delivery_repo):
        """All attempts fail: 3 POSTs, 3 failed delivery logs."""
        mock_http_client.post.side_effect = Exception("Connection refused")

        with patch("flydesk.callbacks.dispatcher.asyncio.sleep", new_callable=AsyncMock):
            await dispatcher._deliver_with_retries(
                "cb-1", "https://example.com/hook", "secret", "email.received", {}
            )

        assert mock_http_client.post.call_count == 3
        assert mock_delivery_repo.record.call_count == 3
        # All records should be "failed"
        for call in mock_delivery_repo.record.call_args_list:
            assert call[1]["status"] == "failed"

    async def test_works_without_delivery_repo(self, mock_settings_repo, mock_http_client):
        """When delivery_repo is None, retries still work (no logging)."""
        dispatcher = CallbackDispatcher(
            settings_repo=mock_settings_repo,
            http_client=mock_http_client,
            delivery_repo=None,
        )
        mock_http_client.post.return_value = MagicMock(status_code=200)

        await dispatcher._deliver_with_retries(
            "cb-1", "https://example.com/hook", "secret", "email.received", {}
        )

        assert mock_http_client.post.call_count == 1


class TestDispatch:
    async def test_dispatch_calls_deliver_with_retries(self, dispatcher, mock_settings_repo, mock_http_client):
        """dispatch() should fire tasks that use _deliver_with_retries."""
        mock_http_client.post.return_value = MagicMock(status_code=200)

        await dispatcher.dispatch("email.received", {"from": "user@example.com"})
        # Allow the create_task to run
        await asyncio.sleep(0.1)

        mock_http_client.post.assert_called_once()

    async def test_dispatch_skips_disabled_callbacks(self, dispatcher, mock_settings_repo, mock_http_client):
        """Disabled callbacks should not be dispatched."""
        mock_settings_repo.get_email_settings.return_value = MagicMock(
            outbound_callbacks=[
                {"id": "cb-1", "url": "https://example.com/hook", "secret": "s", "events": [], "enabled": False}
            ]
        )
        await dispatcher.dispatch("email.received", {})
        await asyncio.sleep(0.1)
        mock_http_client.post.assert_not_called()

    async def test_dispatch_filters_by_event(self, dispatcher, mock_settings_repo, mock_http_client):
        """Callbacks only fire for matching events."""
        # The fixture callback only subscribes to "email.received"
        await dispatcher.dispatch("agent.error", {})
        await asyncio.sleep(0.1)
        mock_http_client.post.assert_not_called()
