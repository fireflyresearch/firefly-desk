# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""ORM models for business process discovery."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flydesk.models.base import Base

# Use JSON for SQLite compatibility in tests, JSONB in production
_JSON = JSONB().with_variant(Text, "sqlite")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BusinessProcessRow(Base):
    """ORM row for the ``business_processes`` table."""

    __tablename__ = "business_processes"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(255), nullable=False, default="", index=True)
    workspace_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="auto_discovered")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="discovered", index=True)
    tags_json: Mapped[str | None] = mapped_column(_JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    steps: Mapped[list[ProcessStepRow]] = relationship(
        "ProcessStepRow",
        back_populates="process",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    dependencies: Mapped[list[ProcessDependencyRow]] = relationship(
        "ProcessDependencyRow",
        back_populates="process",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ProcessStepRow(Base):
    """ORM row for the ``process_steps`` table."""

    __tablename__ = "process_steps"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    process_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("business_processes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    step_type: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    system_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    endpoint_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inputs_json: Mapped[str | None] = mapped_column(_JSON, nullable=True)
    outputs_json: Mapped[str | None] = mapped_column(_JSON, nullable=True)

    process: Mapped[BusinessProcessRow] = relationship(
        "BusinessProcessRow", back_populates="steps"
    )


class ProcessDependencyRow(Base):
    """ORM row for the ``process_dependencies`` table."""

    __tablename__ = "process_dependencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    process_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("business_processes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_step_id: Mapped[str] = mapped_column(String(255), nullable=False)
    target_step_id: Mapped[str] = mapped_column(String(255), nullable=False)
    condition: Mapped[str | None] = mapped_column(Text, nullable=True)

    process: Mapped[BusinessProcessRow] = relationship(
        "BusinessProcessRow", back_populates="dependencies"
    )
