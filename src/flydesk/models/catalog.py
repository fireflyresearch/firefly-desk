# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""ORM models for the Service Catalog."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from flydesk.models.base import Base

# Use JSON for SQLite compatibility in tests, JSONB in production
_JSON = JSONB().with_variant(Text, "sqlite")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ExternalSystemRow(Base):
    """ORM row for the ``external_systems`` table."""

    __tablename__ = "external_systems"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    auth_config: Mapped[dict | None] = mapped_column(_JSON, nullable=True)
    health_check_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tags: Mapped[list] = mapped_column(_JSON, nullable=False, default=list)
    agent_enabled: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    metadata_: Mapped[dict] = mapped_column("metadata", _JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class ServiceEndpointRow(Base):
    """ORM row for the ``service_endpoints`` table."""

    __tablename__ = "service_endpoints"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    system_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(2048), nullable=False)
    path_params: Mapped[dict | None] = mapped_column(_JSON, nullable=True)
    query_params: Mapped[dict | None] = mapped_column(_JSON, nullable=True)
    request_body: Mapped[dict | None] = mapped_column(_JSON, nullable=True)
    response_schema: Mapped[dict | None] = mapped_column(_JSON, nullable=True)
    when_to_use: Mapped[str] = mapped_column(Text, nullable=False)
    examples: Mapped[list] = mapped_column(_JSON, nullable=False, default=list)
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False)
    required_permissions: Mapped[list] = mapped_column(_JSON, nullable=False)
    rate_limit: Mapped[dict | None] = mapped_column(_JSON, nullable=True)
    timeout_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=30.0)
    retry_policy: Mapped[dict | None] = mapped_column(_JSON, nullable=True)
    tags: Mapped[list] = mapped_column(_JSON, nullable=False, default=list)
    protocol_type: Mapped[str] = mapped_column(String(20), nullable=False, default="rest")
    graphql_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    graphql_operation_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    soap_action: Mapped[str | None] = mapped_column(String(500), nullable=True)
    soap_body_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    grpc_service: Mapped[str | None] = mapped_column(String(255), nullable=True)
    grpc_method_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class CredentialRow(Base):
    """ORM row for the ``credentials`` table."""

    __tablename__ = "credentials"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    system_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    credential_type: Mapped[str] = mapped_column(String(50), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_rotated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
