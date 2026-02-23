# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Authentication models for Firefly Desk."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from flydesk.rbac.models import AccessScopes


class UserSession(BaseModel):
    """Hydrated from the OIDC token on every request."""

    user_id: str
    email: str
    display_name: str
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    access_scopes: AccessScopes = Field(default_factory=AccessScopes)
    tenant_id: str | None = None
    picture_url: str | None = None
    department: str | None = None
    title: str | None = None
    session_id: str
    token_expires_at: datetime
    raw_claims: dict[str, Any] = Field(default_factory=dict)
