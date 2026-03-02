"""Tests for DeskAgent integration with the model router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestDeskAgentRouterIntegration:
    @pytest.mark.asyncio
    async def test_desk_agent_accepts_model_router(self):
        from flydesk.agent.desk_agent import DeskAgent

        mock_router = AsyncMock()

        agent = DeskAgent(
            context_enricher=MagicMock(),
            prompt_builder=MagicMock(),
            tool_factory=MagicMock(),
            widget_parser=MagicMock(),
            audit_logger=MagicMock(),
            model_router=mock_router,
        )
        assert agent._model_router is mock_router

    @pytest.mark.asyncio
    async def test_desk_agent_model_router_defaults_to_none(self):
        from flydesk.agent.desk_agent import DeskAgent

        agent = DeskAgent(
            context_enricher=MagicMock(),
            prompt_builder=MagicMock(),
            tool_factory=MagicMock(),
            widget_parser=MagicMock(),
            audit_logger=MagicMock(),
        )
        assert agent._model_router is None

    @pytest.mark.asyncio
    async def test_route_model_returns_none_when_no_router(self):
        from flydesk.agent.desk_agent import DeskAgent

        agent = DeskAgent(
            context_enricher=MagicMock(),
            prompt_builder=MagicMock(),
            tool_factory=MagicMock(),
            widget_parser=MagicMock(),
            audit_logger=MagicMock(),
        )
        model_override, decision = await agent._route_model("Hello", None)
        assert model_override is None
        assert decision is None

    @pytest.mark.asyncio
    async def test_route_model_returns_decision(self):
        from flydesk.agent.desk_agent import DeskAgent
        from flydesk.agent.router.models import ComplexityTier, RoutingDecision

        mock_decision = RoutingDecision(
            model_string="anthropic:claude-haiku-4-5-20251001",
            tier=ComplexityTier.FAST,
            confidence=0.9,
            reasoning="Simple",
            classifier_model="anthropic:claude-haiku-4-5-20251001",
            classifier_latency_ms=150.0,
            classifier_tokens=30,
        )
        mock_router = AsyncMock()
        mock_router.route = AsyncMock(return_value=mock_decision)

        agent = DeskAgent(
            context_enricher=MagicMock(),
            prompt_builder=MagicMock(),
            tool_factory=MagicMock(),
            widget_parser=MagicMock(),
            audit_logger=MagicMock(),
            model_router=mock_router,
        )
        model_override, decision = await agent._route_model("Hello", None)
        assert model_override == "anthropic:claude-haiku-4-5-20251001"
        assert decision is mock_decision

    @pytest.mark.asyncio
    async def test_route_model_handles_router_failure(self):
        from flydesk.agent.desk_agent import DeskAgent

        mock_router = AsyncMock()
        mock_router.route = AsyncMock(side_effect=RuntimeError("boom"))

        agent = DeskAgent(
            context_enricher=MagicMock(),
            prompt_builder=MagicMock(),
            tool_factory=MagicMock(),
            widget_parser=MagicMock(),
            audit_logger=MagicMock(),
            model_router=mock_router,
        )
        model_override, decision = await agent._route_model("Hello", None)
        assert model_override is None
        assert decision is None
