# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""ORM model for tracking dismissed notifications."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from flydesk.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NotificationDismissalRow(Base):
    """ORM row for the ``notification_dismissals`` table.

    Tracks which notification IDs (job IDs or workflow IDs) have been
    dismissed by users so they no longer appear in the notifications list.
    """

    __tablename__ = "notification_dismissals"
    __table_args__ = (UniqueConstraint("notification_id", name="uq_notification_dismissals_nid"),)

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    notification_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    dismissed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
