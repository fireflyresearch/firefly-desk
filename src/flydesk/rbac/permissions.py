# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Permission enum, built-in role definitions, and scope resolution helpers."""

from __future__ import annotations

from enum import StrEnum

from flydesk.rbac.models import AccessScopes, Role


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
    JOBS_READ = "jobs:read"
    JOBS_CANCEL = "jobs:cancel"
    PROCESSES_READ = "processes:read"
    PROCESSES_WRITE = "processes:write"
    ADMIN_USERS = "admin:users"
    ADMIN_SETTINGS = "admin:settings"
    ADMIN_ROLES = "admin:roles"
    ADMIN_SSO = "admin:sso"
    ADMIN_LLM = "admin:llm"
    ADMIN_DASHBOARD = "admin:dashboard"
    ADMIN_GIT_PROVIDERS = "admin:git_providers"


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
        description="Operational access to catalog, knowledge, exports, jobs, and chat.",
        permissions=[
            "knowledge:read",
            "catalog:read",
            "catalog:write",
            "exports:create",
            "exports:download",
            "chat:send",
            "audit:read",
            "jobs:read",
            "jobs:cancel",
            "processes:read",
            "processes:write",
        ],
        is_builtin=True,
    ),
    Role(
        id="role-viewer",
        name="viewer",
        display_name="Viewer",
        description="Read-only access to knowledge, catalog, jobs, and chat.",
        permissions=[
            "knowledge:read",
            "catalog:read",
            "chat:send",
            "jobs:read",
            "processes:read",
        ],
        is_builtin=True,
    ),
]


def merge_access_scopes(scopes_list: list[AccessScopes]) -> AccessScopes:
    """Merge multiple :class:`AccessScopes` into a single union.

    The merge follows the *most permissive* strategy: if **any** scope in the
    list has an empty field (= unrestricted), the merged result is also
    unrestricted for that dimension.  Otherwise, the allowed values are unioned.
    """
    if not scopes_list:
        return AccessScopes()

    systems: set[str] = set()
    knowledge_tags: set[str] = set()
    skill_tags: set[str] = set()
    systems_unrestricted = False
    knowledge_unrestricted = False
    skills_unrestricted = False

    for scope in scopes_list:
        if not scope.systems:
            systems_unrestricted = True
        else:
            systems.update(scope.systems)

        if not scope.knowledge_tags:
            knowledge_unrestricted = True
        else:
            knowledge_tags.update(scope.knowledge_tags)

        if not scope.skill_tags:
            skills_unrestricted = True
        else:
            skill_tags.update(scope.skill_tags)

    return AccessScopes(
        systems=[] if systems_unrestricted else sorted(systems),
        knowledge_tags=[] if knowledge_unrestricted else sorted(knowledge_tags),
        skill_tags=[] if skills_unrestricted else sorted(skill_tags),
    )


def is_admin(permissions: list[str]) -> bool:
    """Return True if the permission set contains the wildcard (superuser)."""
    return "*" in permissions
