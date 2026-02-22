# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Authentication models for Firefly Desk."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UserSession(BaseModel):
    """Hydrated from the OIDC token on every request."""

    user_id: str
    email: str
    display_name: str
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    tenant_id: str | None = None
    session_id: str
    token_expires_at: datetime
    raw_claims: dict[str, Any] = Field(default_factory=dict)
