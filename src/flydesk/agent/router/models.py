"""Domain models for the smart model router."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ComplexityTier(StrEnum):
    """Model capability tiers for routing decisions."""

    FAST = "fast"
    BALANCED = "balanced"
    POWERFUL = "powerful"


class ClassificationResult(BaseModel):
    """Result from the complexity classifier."""

    tier: ComplexityTier
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class RoutingDecision(BaseModel):
    """Complete routing decision with metadata for audit logging."""

    model_string: str
    tier: ComplexityTier
    confidence: float
    reasoning: str
    classifier_model: str
    classifier_latency_ms: float
    classifier_tokens: int


class RoutingConfig(BaseModel):
    """Runtime configuration for the model router."""

    enabled: bool = False
    classifier_model: str | None = None
    default_tier: str = "balanced"
    tier_mappings: dict[str, str] = Field(default_factory=dict)
    updated_at: datetime | None = None
