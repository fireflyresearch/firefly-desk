# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""ORM models for exports and export templates."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from flydek.models.base import Base

# Use JSON for SQLite compatibility in tests, JSONB in production
_JSON = JSONB().with_variant(Text, "sqlite")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ExportRow(Base):
    """ORM row for the ``exports`` table."""

    __tablename__ = "exports"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    template_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    file_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_data: Mapped[dict] = mapped_column(_JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ExportTemplateRow(Base):
    """ORM row for the ``export_templates`` table."""

    __tablename__ = "export_templates"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    column_mapping: Mapped[dict] = mapped_column(_JSON, nullable=False, default=dict)
    header_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    footer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
