# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""ORM model for custom tools."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from flydesk.models.base import Base

_JSON = JSONB().with_variant(Text, "sqlite")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CustomToolRow(Base):
    """ORM row for the ``custom_tools`` table."""

    __tablename__ = "custom_tools"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    python_code: Mapped[str] = mapped_column(Text, nullable=False, default="")
    parameters: Mapped[dict] = mapped_column(_JSON, nullable=False, default=dict)
    output_schema: Mapped[dict] = mapped_column(_JSON, nullable=False, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    max_memory_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=256)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
