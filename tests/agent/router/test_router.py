"""Tests for the ModelRouter orchestrator."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from flydesk.agent.router.models import (
    ClassificationResult,
    ComplexityTier,
    RoutingConfig,
    RoutingDecision,
)


@pytest.fixture
def mock_classifier():
    classifier = AsyncMock()
    classifier.classify = AsyncMock(
        return_value=ClassificationResult(
            tier=ComplexityTier.FAST,
            confidence=0.9,
            reasoning="Simple question",
        )
    )
    return classifier


@pytest.fixture
def mock_config_repo():
    repo = AsyncMock()
    repo.get_config = AsyncMock(
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
    return repo


class TestModelRouter:
    async def test_route_returns_decision(self, mock_classifier, mock_config_repo):
        from flydesk.agent.router.router import ModelRouter

        router = ModelRouter(classifier=mock_classifier, config_repo=mock_config_repo)
        decision = await router.route(
            message="Hello!",
            tool_count=3,
            tool_names=["search"],
            turn_count=0,
        )
        assert isinstance(decision, RoutingDecision)
        assert decision.tier == ComplexityTier.FAST
        assert decision.model_string == "anthropic:claude-haiku-4-5-20251001"

    async def test_route_returns_none_when_disabled(self, mock_classifier, mock_config_repo):
        from flydesk.agent.router.router import ModelRouter

        mock_config_repo.get_config = AsyncMock(
            return_value=RoutingConfig(enabled=False)
        )
        router = ModelRouter(classifier=mock_classifier, config_repo=mock_config_repo)
        decision = await router.route(
            message="Hello!",
            tool_count=0,
            tool_names=[],
            turn_count=0,
        )
        assert decision is None

    async def test_route_returns_none_when_no_config(self, mock_classifier, mock_config_repo):
        from flydesk.agent.router.router import ModelRouter

        mock_config_repo.get_config = AsyncMock(return_value=None)
        router = ModelRouter(classifier=mock_classifier, config_repo=mock_config_repo)
        decision = await router.route(
            message="Hello!",
            tool_count=0,
            tool_names=[],
            turn_count=0,
        )
        assert decision is None

    async def test_route_falls_back_on_low_confidence(self, mock_classifier, mock_config_repo):
        from flydesk.agent.router.router import ModelRouter

        mock_classifier.classify = AsyncMock(
            return_value=ClassificationResult(
                tier=ComplexityTier.FAST,
                confidence=0.3,  # Below 0.5 threshold
                reasoning="Uncertain",
            )
        )
        router = ModelRouter(classifier=mock_classifier, config_repo=mock_config_repo)
        decision = await router.route(
            message="Ambiguous request",
            tool_count=0,
            tool_names=[],
            turn_count=0,
        )
        assert decision is not None
        assert decision.tier == ComplexityTier.BALANCED
        assert decision.model_string == "anthropic:claude-sonnet-4-6"

    async def test_route_falls_back_when_tier_not_mapped(self, mock_classifier, mock_config_repo):
        from flydesk.agent.router.router import ModelRouter

        mock_config_repo.get_config = AsyncMock(
            return_value=RoutingConfig(
                enabled=True,
                tier_mappings={"balanced": "anthropic:claude-sonnet-4-6"},
            )
        )
        mock_classifier.classify = AsyncMock(
            return_value=ClassificationResult(
                tier=ComplexityTier.FAST,
                confidence=0.9,
                reasoning="Simple",
            )
        )
        router = ModelRouter(classifier=mock_classifier, config_repo=mock_config_repo)
        decision = await router.route(
            message="Hello",
            tool_count=0,
            tool_names=[],
            turn_count=0,
        )
        assert decision is not None
        assert decision.tier == ComplexityTier.BALANCED

    async def test_is_enabled_checks_config(self, mock_classifier, mock_config_repo):
        from flydesk.agent.router.router import ModelRouter

        router = ModelRouter(classifier=mock_classifier, config_repo=mock_config_repo)
        assert await router.is_enabled() is True

        mock_config_repo.get_config = AsyncMock(
            return_value=RoutingConfig(enabled=False)
        )
        assert await router.is_enabled() is False

    async def test_route_handles_classifier_exception(self, mock_classifier, mock_config_repo):
        from flydesk.agent.router.router import ModelRouter

        mock_classifier.classify = AsyncMock(side_effect=RuntimeError("boom"))
        router = ModelRouter(classifier=mock_classifier, config_repo=mock_config_repo)
        decision = await router.route(
            message="Hello",
            tool_count=0,
            tool_names=[],
            turn_count=0,
        )
        assert decision is not None
        assert decision.tier == ComplexityTier.BALANCED

    async def test_route_returns_none_when_no_tier_mappings(self, mock_classifier, mock_config_repo):
        from flydesk.agent.router.router import ModelRouter

        mock_config_repo.get_config = AsyncMock(
            return_value=RoutingConfig(enabled=True, tier_mappings={})
        )
        router = ModelRouter(classifier=mock_classifier, config_repo=mock_config_repo)
        decision = await router.route(
            message="Hello",
            tool_count=0,
            tool_names=[],
            turn_count=0,
        )
        assert decision is None
