"""ORM model for the model routing configuration table."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from flydesk.models.base import Base

_JSON = JSONB().with_variant(Text, "sqlite")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ModelRoutingConfigRow(Base):
    """ORM row for the ``model_routing_config`` table."""

    __tablename__ = "model_routing_config"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, insert_default=False)
    classifier_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    default_tier: Mapped[str] = mapped_column(String(50), insert_default="balanced")
    tier_mappings: Mapped[dict] = mapped_column(_JSON, nullable=False, insert_default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), insert_default=_utcnow, onupdate=_utcnow,
    )

    def __init__(self, **kwargs: object) -> None:
        if "enabled" not in kwargs:
            kwargs["enabled"] = False
        if "default_tier" not in kwargs:
            kwargs["default_tier"] = "balanced"
        if "tier_mappings" not in kwargs:
            kwargs["tier_mappings"] = {}
        super().__init__(**kwargs)
