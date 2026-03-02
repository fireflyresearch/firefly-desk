"""Tests for the LLM-based complexity classifier."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from flydesk.agent.router.models import ClassificationResult, ComplexityTier


@pytest.fixture
def mock_agent_factory():
    """Mock DeskAgentFactory that returns a mock agent."""
    factory = AsyncMock()
    agent = AsyncMock()
    result = MagicMock()
    result.output = '{"tier": "fast", "confidence": 0.95, "reasoning": "Simple greeting"}'
    agent.run = AsyncMock(return_value=result)
    factory.create_agent = AsyncMock(return_value=agent)
    return factory


class TestComplexityClassifier:
    async def test_classify_simple_message(self, mock_agent_factory):
        from flydesk.agent.router.classifier import ComplexityClassifier

        classifier = ComplexityClassifier(mock_agent_factory)
        result = await classifier.classify(
            message="Hello!",
            tool_count=5,
            tool_names=["search", "create_ticket"],
            turn_count=0,
        )
        assert isinstance(result, ClassificationResult)
        assert result.tier == ComplexityTier.FAST
        assert result.confidence == 0.95

    async def test_classify_returns_balanced_on_agent_none(self, mock_agent_factory):
        from flydesk.agent.router.classifier import ComplexityClassifier

        mock_agent_factory.create_agent = AsyncMock(return_value=None)

        classifier = ComplexityClassifier(mock_agent_factory)
        result = await classifier.classify(
            message="Test",
            tool_count=0,
            tool_names=[],
            turn_count=0,
        )
        assert result.tier == ComplexityTier.BALANCED
        assert result.confidence == 0.0

    async def test_classify_handles_invalid_json(self, mock_agent_factory):
        from flydesk.agent.router.classifier import ComplexityClassifier

        agent = AsyncMock()
        result_obj = MagicMock()
        result_obj.output = "not valid json at all"
        agent.run = AsyncMock(return_value=result_obj)
        mock_agent_factory.create_agent = AsyncMock(return_value=agent)

        classifier = ComplexityClassifier(mock_agent_factory)
        result = await classifier.classify(
            message="Test",
            tool_count=0,
            tool_names=[],
            turn_count=0,
        )
        assert result.tier == ComplexityTier.BALANCED
        assert result.confidence == 0.0

    async def test_classify_handles_exception(self, mock_agent_factory):
        from flydesk.agent.router.classifier import ComplexityClassifier

        mock_agent_factory.create_agent = AsyncMock(side_effect=RuntimeError("boom"))

        classifier = ComplexityClassifier(mock_agent_factory)
        result = await classifier.classify(
            message="Test",
            tool_count=0,
            tool_names=[],
            turn_count=0,
        )
        assert result.tier == ComplexityTier.BALANCED
        assert result.confidence == 0.0

    async def test_classify_uses_custom_classifier_model(self, mock_agent_factory):
        from flydesk.agent.router.classifier import ComplexityClassifier

        classifier = ComplexityClassifier(
            mock_agent_factory,
            classifier_model="openai:gpt-4o-mini",
        )
        await classifier.classify(
            message="Hello",
            tool_count=0,
            tool_names=[],
            turn_count=0,
        )
        call_kwargs = mock_agent_factory.create_agent.call_args
        assert call_kwargs.kwargs.get("model_override") == "openai:gpt-4o-mini"

    async def test_classify_strips_markdown_fences(self, mock_agent_factory):
        from flydesk.agent.router.classifier import ComplexityClassifier

        agent = AsyncMock()
        result_obj = MagicMock()
        result_obj.output = '```json\n{"tier": "powerful", "confidence": 0.8, "reasoning": "Complex"}\n```'
        agent.run = AsyncMock(return_value=result_obj)
        mock_agent_factory.create_agent = AsyncMock(return_value=agent)

        classifier = ComplexityClassifier(mock_agent_factory)
        result = await classifier.classify(
            message="Complex analysis request",
            tool_count=10,
            tool_names=["query_db", "create_chart"],
            turn_count=5,
        )
        assert result.tier == ComplexityTier.POWERFUL
        assert result.confidence == 0.8

    async def test_classify_clamps_confidence(self, mock_agent_factory):
        from flydesk.agent.router.classifier import ComplexityClassifier

        agent = AsyncMock()
        result_obj = MagicMock()
        result_obj.output = '{"tier": "fast", "confidence": 1.5, "reasoning": "Very sure"}'
        agent.run = AsyncMock(return_value=result_obj)
        mock_agent_factory.create_agent = AsyncMock(return_value=agent)

        classifier = ComplexityClassifier(mock_agent_factory)
        result = await classifier.classify(
            message="Hello",
            tool_count=0,
            tool_names=[],
            turn_count=0,
        )
        assert result.confidence == 1.0  # Clamped to max

    async def test_classify_handles_unknown_tier(self, mock_agent_factory):
        from flydesk.agent.router.classifier import ComplexityClassifier

        agent = AsyncMock()
        result_obj = MagicMock()
        result_obj.output = '{"tier": "extreme", "confidence": 0.9, "reasoning": "Unknown tier"}'
        agent.run = AsyncMock(return_value=result_obj)
        mock_agent_factory.create_agent = AsyncMock(return_value=agent)

        classifier = ComplexityClassifier(mock_agent_factory)
        result = await classifier.classify(
            message="Test",
            tool_count=0,
            tool_names=[],
            turn_count=0,
        )
        # Unknown tier should fall back to BALANCED
        assert result.tier == ComplexityTier.BALANCED
