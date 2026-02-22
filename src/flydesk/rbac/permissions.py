# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Permission enum and built-in role definitions."""

from __future__ import annotations

from enum import StrEnum

from flydesk.rbac.models import Role


class Permission(StrEnum):
    """All discrete permissions recognised by the system."""

    KNOWLEDGE_READ = "knowledge:read"
    KNOWLEDGE_WRITE = "knowledge:write"
    KNOWLEDGE_DELETE = "knowledge:delete"
    CATALOG_READ = "catalog:read"
    CATALOG_WRITE = "catalog:write"
    CATALOG_DELETE = "catalog:delete"
    CHAT_SEND = "chat:send"
    EXPORTS_CREATE = "exports:create"
    EXPORTS_DOWNLOAD = "exports:download"
    EXPORTS_DELETE = "exports:delete"
    EXPORTS_TEMPLATES = "exports:templates"
    AUDIT_READ = "audit:read"
    CREDENTIALS_READ = "credentials:read"
    CREDENTIALS_WRITE = "credentials:write"
    ADMIN_USERS = "admin:users"
    ADMIN_SETTINGS = "admin:settings"
    ADMIN_ROLES = "admin:roles"
    ADMIN_SSO = "admin:sso"
    ADMIN_LLM = "admin:llm"
    ADMIN_DASHBOARD = "admin:dashboard"


BUILTIN_ROLES: list[Role] = [
    Role(
        id="role-admin",
        name="admin",
        display_name="Administrator",
        description="Full system access.",
        permissions=["*"],
        is_builtin=True,
    ),
    Role(
        id="role-operator",
        name="operator",
        display_name="Operator",
        description="Operational access to catalog, knowledge, exports, and chat.",
        permissions=[
            "knowledge:read",
            "catalog:read",
            "catalog:write",
            "exports:create",
            "exports:download",
            "chat:send",
            "audit:read",
        ],
        is_builtin=True,
    ),
    Role(
        id="role-viewer",
        name="viewer",
        display_name="Viewer",
        description="Read-only access to knowledge, catalog, and chat.",
        permissions=[
            "knowledge:read",
            "catalog:read",
            "chat:send",
        ],
        is_builtin=True,
    ),
]
