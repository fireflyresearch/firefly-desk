# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""ORM models for the Knowledge Graph."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from flydek.models.base import Base

_JSON = JSONB().with_variant(Text, "sqlite")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EntityRow(Base):
    __tablename__ = "kg_entities"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    properties: Mapped[dict] = mapped_column(_JSON, nullable=False, default=dict)
    source_system: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    mention_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class RelationRow(Base):
    __tablename__ = "kg_relations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(100), nullable=False)
    properties: Mapped[dict] = mapped_column(_JSON, nullable=False, default=dict)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
