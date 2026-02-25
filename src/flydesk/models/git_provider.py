# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""ORM model for Git provider configuration."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from flydesk.models.base import Base

# Use JSON for SQLite compatibility in tests, JSONB in production
_JSON = JSONB().with_variant(Text, "sqlite")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GitProviderRow(Base):
    """ORM row for the ``git_providers`` table."""

    __tablename__ = "git_providers"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    provider_type: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    auth_method: Mapped[str] = mapped_column(String(20), nullable=False, default="oauth")
    client_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    client_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    oauth_authorize_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    oauth_token_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    scopes: Mapped[list | None] = mapped_column(_JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
