"""Tests for model router domain models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_complexity_tier_values():
    from flydesk.agent.router.models import ComplexityTier

    assert ComplexityTier.FAST == "fast"
    assert ComplexityTier.BALANCED == "balanced"
    assert ComplexityTier.POWERFUL == "powerful"


def test_classification_result_valid():
    from flydesk.agent.router.models import ClassificationResult, ComplexityTier

    result = ClassificationResult(
        tier=ComplexityTier.FAST,
        confidence=0.95,
        reasoning="Simple greeting",
    )
    assert result.tier == ComplexityTier.FAST
    assert result.confidence == 0.95


def test_classification_result_rejects_invalid_confidence():
    from flydesk.agent.router.models import ClassificationResult, ComplexityTier

    with pytest.raises(ValidationError):
        ClassificationResult(
            tier=ComplexityTier.BALANCED,
            confidence=1.5,
            reasoning="test",
        )


def test_routing_decision_fields():
    from flydesk.agent.router.models import ComplexityTier, RoutingDecision

    decision = RoutingDecision(
        model_string="anthropic:claude-haiku-4-5-20251001",
        tier=ComplexityTier.FAST,
        confidence=0.9,
        reasoning="Simple query",
        classifier_model="anthropic:claude-haiku-4-5-20251001",
        classifier_latency_ms=180.0,
        classifier_tokens=45,
    )
    assert decision.model_string == "anthropic:claude-haiku-4-5-20251001"
    assert decision.tier == ComplexityTier.FAST


def test_routing_config_defaults():
    from flydesk.agent.router.models import RoutingConfig

    config = RoutingConfig()
    assert config.enabled is False
    assert config.default_tier == "balanced"
    assert config.tier_mappings == {}


def test_routing_config_with_tiers():
    from flydesk.agent.router.models import RoutingConfig

    config = RoutingConfig(
        enabled=True,
        classifier_model="anthropic:claude-haiku-4-5-20251001",
        tier_mappings={
            "fast": "anthropic:claude-haiku-4-5-20251001",
            "balanced": "anthropic:claude-sonnet-4-6",
            "powerful": "anthropic:claude-opus-4-6",
        },
    )
    assert config.enabled is True
    assert len(config.tier_mappings) == 3
