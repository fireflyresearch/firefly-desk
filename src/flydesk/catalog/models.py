# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Pydantic domain models for the Service Catalog."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from flydesk.catalog.enums import AuthType, HttpMethod, ProtocolType, RiskLevel, SystemStatus


class ParamSchema(BaseModel):
    """Schema for a single API parameter."""

    type: str
    description: str
    required: bool = True
    default: Any | None = None
    enum: list[str] | None = None
    pattern: str | None = None


class RateLimit(BaseModel):
    """Rate limit configuration for an endpoint."""

    max_requests: int
    window_seconds: int


class RetryPolicy(BaseModel):
    """Retry policy for an endpoint."""

    max_retries: int = 3
    backoff_factor: float = 1.0


class AuthConfig(BaseModel):
    """Authentication configuration for an external system."""

    auth_type: AuthType
    credential_id: str
    token_url: str | None = None
    scopes: list[str] | None = None
    auth_headers: dict[str, str] | None = None
    auth_params: dict[str, str] | None = None


class ExternalSystem(BaseModel):
    """A backend system the agent can interact with."""

    id: str
    name: str
    description: str
    base_url: str
    auth_config: AuthConfig
    health_check_path: str | None = None
    tags: list[str] = Field(default_factory=list)
    status: SystemStatus = SystemStatus.ACTIVE
    metadata: dict[str, Any] = Field(default_factory=dict)


class ServiceEndpoint(BaseModel):
    """A single operation the agent can perform on an external system."""

    id: str
    system_id: str
    name: str
    description: str
    method: HttpMethod
    path: str

    path_params: dict[str, ParamSchema] | None = None
    query_params: dict[str, ParamSchema] | None = None
    request_body: dict[str, Any] | None = None
    response_schema: dict[str, Any] | None = None

    when_to_use: str
    examples: list[str] = Field(default_factory=list)
    risk_level: RiskLevel
    required_permissions: list[str]

    protocol_type: ProtocolType = ProtocolType.REST
    rate_limit: RateLimit | None = None
    timeout_seconds: float = 30.0
    retry_policy: RetryPolicy | None = None
    tags: list[str] = Field(default_factory=list)

    # GraphQL-specific fields
    graphql_query: str | None = None
    graphql_operation_name: str | None = None

    # SOAP-specific fields
    soap_action: str | None = None
    soap_body_template: str | None = None

    # gRPC-specific fields
    grpc_service: str | None = None
    grpc_method_name: str | None = None


class Credential(BaseModel):
    """Encrypted credential for system authentication."""

    id: str
    system_id: str
    name: str
    encrypted_value: str
    credential_type: str
    expires_at: datetime | None = None
    last_rotated: datetime | None = None
