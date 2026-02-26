# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Enumerations for the Service Catalog."""

from __future__ import annotations

from enum import StrEnum


class SystemStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"
    DEPRECATED = "deprecated"
    DEGRADED = "degraded"


VALID_TRANSITIONS: dict[SystemStatus, set[SystemStatus]] = {
    SystemStatus.DRAFT: {SystemStatus.ACTIVE},
    SystemStatus.ACTIVE: {SystemStatus.DISABLED, SystemStatus.DEPRECATED, SystemStatus.DEGRADED},
    SystemStatus.DISABLED: {SystemStatus.ACTIVE, SystemStatus.DEPRECATED},
    SystemStatus.DEPRECATED: set(),  # terminal state
    SystemStatus.DEGRADED: {SystemStatus.ACTIVE, SystemStatus.DISABLED},
}


class AuthType(StrEnum):
    NONE = "none"
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    BASIC = "basic"
    BEARER = "bearer"
    MUTUAL_TLS = "mutual_tls"


class HttpMethod(StrEnum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class RiskLevel(StrEnum):
    READ = "read"
    LOW_WRITE = "low_write"
    HIGH_WRITE = "high_write"
    DESTRUCTIVE = "destructive"


class ProtocolType(StrEnum):
    REST = "rest"
    GRAPHQL = "graphql"
    SOAP = "soap"
    GRPC = "grpc"
    WEBSOCKET = "websocket"
