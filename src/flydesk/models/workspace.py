# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""ORM models for workspace organization."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from flydesk.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WorkspaceRow(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    icon: Mapped[str] = mapped_column(String(50), nullable=False, default="folder")
    color: Mapped[str] = mapped_column(String(20), nullable=False, default="#6366f1")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class WorkspaceRoleRow(Base):
    __tablename__ = "workspace_roles"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String(255), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    role_name: Mapped[str] = mapped_column(String(255), nullable=False)


class WorkspaceUserRow(Base):
    __tablename__ = "workspace_users"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String(255), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
