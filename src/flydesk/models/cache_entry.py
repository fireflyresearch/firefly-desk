# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""ORM model for the cache_entries table."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from flydesk.models.base import Base


class CacheEntryRow(Base):
    """Database-backed cache entry."""

    __tablename__ = "cache_entries"
    __table_args__ = (
        UniqueConstraint("namespace", "cache_key", name="uq_cache_ns_key"),
        Index("ix_cache_entries_expires_at", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    namespace: Mapped[str] = mapped_column(String(50), nullable=False)
    cache_key: Mapped[str] = mapped_column(String(255), nullable=False)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
