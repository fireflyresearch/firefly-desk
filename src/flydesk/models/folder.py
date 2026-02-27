# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""ORM model for Conversation Folders."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from flydesk.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ConversationFolderRow(Base):
    """ORM row for the ``conversation_folders`` table."""

    __tablename__ = "conversation_folders"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    icon: Mapped[str] = mapped_column(String(50), nullable=False, default="folder")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
