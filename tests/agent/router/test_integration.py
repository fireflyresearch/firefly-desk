"""End-to-end integration test for the model router pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from flydesk.agent.router.models import ComplexityTier, RoutingConfig


class TestRouterEndToEnd:
    async def test_full_routing_pipeline(self):
        from flydesk.agent.router.classifier import ComplexityClassifier
        from flydesk.agent.router.config import RoutingConfigRepository
        from flydesk.agent.router.router import ModelRouter

        mock_factory = AsyncMock()
        mock_agent = AsyncMock()
        mock_result = MagicMock()
        mock_result.output = '{"tier": "powerful", "confidence": 0.85, "reasoning": "Complex multi-tool request"}'
        mock_agent.run = AsyncMock(return_value=mock_result)
        mock_factory.create_agent = AsyncMock(return_value=mock_agent)

        mock_config_repo = AsyncMock()
        mock_config_repo.get_config = AsyncMock(
            return_value=RoutingConfig(
                enabled=True,
                classifier_model="anthropic:claude-haiku-4-5-20251001",
                tier_mappings={
                    "fast": "anthropic:claude-haiku-4-5-20251001",
                    "balanced": "anthropic:claude-sonnet-4-6",
                    "powerful": "anthropic:claude-opus-4-6",
                },
            )
        )

        classifier = ComplexityClassifier(mock_factory, classifier_model="anthropic:claude-haiku-4-5-20251001")
        router = ModelRouter(classifier=classifier, config_repo=mock_config_repo)

        decision = await router.route(
            message="Analyze all sales data from Q4, create projections, and generate a report",
            tool_count=8,
            tool_names=["query_db", "create_chart", "export_csv", "send_email"],
            turn_count=3,
        )

        assert decision is not None
        assert decision.tier == ComplexityTier.POWERFUL
        assert decision.model_string == "anthropic:claude-opus-4-6"
        assert decision.confidence == 0.85
        assert "Complex" in decision.reasoning

    async def test_disabled_router_returns_none(self):
        from flydesk.agent.router.classifier import ComplexityClassifier
        from flydesk.agent.router.config import RoutingConfigRepository
        from flydesk.agent.router.router import ModelRouter

        mock_factory = AsyncMock()
        mock_config_repo = AsyncMock()
        mock_config_repo.get_config = AsyncMock(
            return_value=RoutingConfig(enabled=False)
        )

        classifier = ComplexityClassifier(mock_factory)
        router = ModelRouter(classifier=classifier, config_repo=mock_config_repo)

        decision = await router.route(
            message="Hello",
            tool_count=0,
            tool_names=[],
            turn_count=0,
        )
        assert decision is None
        mock_factory.create_agent.assert_not_called()

    async def test_imports_from_package(self):
        """Verify all exports are accessible from the package."""
        from flydesk.agent.router import (
            ClassificationResult,
            ComplexityClassifier,
            ComplexityTier,
            ModelRouter,
            RoutingConfig,
            RoutingConfigRepository,
            RoutingDecision,
        )
        assert ComplexityTier.FAST == "fast"
        assert ClassificationResult is not None
        assert RoutingDecision is not None
