"""Tests that title generation uses the FAST tier model when routing is configured."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from flydesk.agent.router.models import RoutingConfig


class TestTitleGenerationRouting:
    async def test_generate_title_uses_fast_model_when_router_configured(self):
        mock_request = MagicMock()
        mock_repo = AsyncMock()
        mock_repo.get_messages = AsyncMock(return_value=[MagicMock(), MagicMock()])

        mock_conv = MagicMock()
        mock_conv.title = "Old Title"
        mock_repo.get_conversation = AsyncMock(return_value=mock_conv)
        mock_repo.update_conversation = AsyncMock()

        mock_routing_repo = AsyncMock()
        mock_routing_repo.get_config = AsyncMock(
            return_value=RoutingConfig(
                enabled=True,
                tier_mappings={"fast": "anthropic:claude-haiku-4-5-20251001"},
            )
        )

        mock_factory = AsyncMock()
        mock_agent = AsyncMock()
        mock_result = MagicMock()
        mock_result.output = "Chat Title"
        mock_agent.run = AsyncMock(return_value=mock_result)
        mock_factory.create_agent = AsyncMock(return_value=mock_agent)

        mock_request.app.state.conversation_repo = mock_repo
        mock_request.app.state.agent_factory = mock_factory
        mock_request.app.state.routing_config_repo = mock_routing_repo
        mock_request.state.user_session = MagicMock(user_id="test")

        from flydesk.api.chat import _generate_title

        title = await _generate_title(mock_request, "conv-1", "Hello world")

        assert title == "Chat Title"
        call_kwargs = mock_factory.create_agent.call_args
        assert call_kwargs.kwargs.get("model_override") == "anthropic:claude-haiku-4-5-20251001"

    async def test_generate_title_works_without_routing(self):
        mock_request = MagicMock()
        mock_repo = AsyncMock()
        mock_repo.get_messages = AsyncMock(return_value=[MagicMock(), MagicMock()])

        mock_conv = MagicMock()
        mock_conv.title = "Old"
        mock_repo.get_conversation = AsyncMock(return_value=mock_conv)
        mock_repo.update_conversation = AsyncMock()

        mock_factory = AsyncMock()
        mock_agent = AsyncMock()
        mock_result = MagicMock()
        mock_result.output = "Title"
        mock_agent.run = AsyncMock(return_value=mock_result)
        mock_factory.create_agent = AsyncMock(return_value=mock_agent)

        mock_request.app.state.conversation_repo = mock_repo
        mock_request.app.state.agent_factory = mock_factory
        mock_request.app.state.routing_config_repo = None  # No routing repo
        mock_request.state.user_session = MagicMock(user_id="test")

        from flydesk.api.chat import _generate_title

        title = await _generate_title(mock_request, "conv-1", "Hello")

        assert title == "Title"
        call_kwargs = mock_factory.create_agent.call_args
        # Should not have model_override when routing is not configured
        assert call_kwargs.kwargs.get("model_override") is None
