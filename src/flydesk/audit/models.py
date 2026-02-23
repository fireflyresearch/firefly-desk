# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Audit event domain models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AuditEventType(StrEnum):
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    CONFIRMATION_REQUESTED = "confirmation_requested"
    CONFIRMATION_RESPONSE = "confirmation_response"
    AGENT_RESPONSE = "agent_response"
    AUTH_LOGIN = "auth_login"
    AUTH_LOGOUT = "auth_logout"
    CATALOG_CHANGE = "catalog_change"
    KNOWLEDGE_UPDATE = "knowledge_update"


class AuditEvent(BaseModel):
    """An immutable audit trail entry."""

    id: str | None = None
    timestamp: datetime | None = None
    event_type: AuditEventType
    user_id: str
    conversation_id: str | None = None
    system_id: str | None = None
    endpoint_id: str | None = None
    action: str
    detail: dict[str, Any] = Field(default_factory=dict)
    risk_level: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
