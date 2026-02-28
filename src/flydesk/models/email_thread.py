# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""ORM model for email thread tracking."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from flydesk.models.base import Base

_JSON = JSONB().with_variant(Text, "sqlite")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EmailThreadRow(Base):
    """ORM row for the ``email_threads`` table."""

    __tablename__ = "email_threads"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email_message_id: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    thread_root_id: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    participants_json: Mapped[str | None] = mapped_column(_JSON, nullable=True)
    channel_metadata_json: Mapped[str | None] = mapped_column(_JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
