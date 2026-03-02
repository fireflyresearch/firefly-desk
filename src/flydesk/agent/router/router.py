"""ModelRouter — orchestrates complexity classification and model selection."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from flydesk.agent.router.models import (
    ClassificationResult,
    ComplexityTier,
    RoutingDecision,
)

if TYPE_CHECKING:
    from flydesk.agent.router.classifier import ComplexityClassifier
    from flydesk.agent.router.config import RoutingConfigRepository

_logger = logging.getLogger(__name__)

_CONFIDENCE_THRESHOLD = 0.5


class ModelRouter:
    """Routes LLM requests to cost-appropriate model tiers."""

    def __init__(
        self,
        classifier: ComplexityClassifier,
        config_repo: RoutingConfigRepository,
    ) -> None:
        self._classifier = classifier
        self._config_repo = config_repo

    async def is_enabled(self) -> bool:
        """Check if routing is enabled in the current config."""
        config = await self._config_repo.get_config()
        return config is not None and config.enabled

    async def route(
        self,
        message: str,
        tool_count: int,
        tool_names: list[str],
        turn_count: int,
    ) -> RoutingDecision | None:
        """Classify and route a message to the appropriate model.

        Returns None if routing is disabled or not configured.
        Falls back to the default tier on any classification failure.
        """
        config = await self._config_repo.get_config()
        if config is None or not config.enabled:
            return None

        if not config.tier_mappings:
            _logger.debug("Routing enabled but no tier mappings configured.")
            return None

        # Classify
        start = time.monotonic()
        try:
            classification = await self._classifier.classify(
                message=message,
                tool_count=tool_count,
                tool_names=tool_names,
                turn_count=turn_count,
            )
        except Exception:
            _logger.warning("Classifier failed; falling back to default tier.", exc_info=True)
            classification = ClassificationResult(
                tier=ComplexityTier(config.default_tier),
                confidence=0.0,
                reasoning="Classifier error — using default tier",
            )
        classifier_latency_ms = round((time.monotonic() - start) * 1000, 1)

        # Apply confidence threshold
        tier = classification.tier
        if classification.confidence < _CONFIDENCE_THRESHOLD:
            _logger.info(
                "Low confidence %.2f for tier %s; falling back to %s",
                classification.confidence, tier, config.default_tier,
            )
            tier = ComplexityTier(config.default_tier)

        # Map tier to model string
        model_string = config.tier_mappings.get(tier.value)
        if model_string is None:
            _logger.info(
                "Tier %s not mapped; falling back to default tier %s",
                tier, config.default_tier,
            )
            tier = ComplexityTier(config.default_tier)
            model_string = config.tier_mappings.get(tier.value)

        if model_string is None:
            _logger.warning("Default tier %s also not mapped; routing disabled for this request.", tier)
            return None

        return RoutingDecision(
            model_string=model_string,
            tier=tier,
            confidence=classification.confidence,
            reasoning=classification.reasoning,
            classifier_model=config.classifier_model or "default",
            classifier_latency_ms=classifier_latency_ms,
            classifier_tokens=0,
        )
