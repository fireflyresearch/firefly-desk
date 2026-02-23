# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Permission-based FastAPI dependency guards for RBAC enforcement."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request


def require_permission(permission: str):
    """FastAPI dependency that enforces a specific permission.

    Returns a ``Depends(...)`` instance that can be placed directly in a
    route's ``dependencies`` list.  The guard checks the ``user_session``
    attached to the request by the auth middleware:

    * **No session** -- 401 Unauthorized
    * **Wildcard ``*`` in permissions** -- access granted (superuser)
    * **Requested permission present** -- access granted
    * **Otherwise** -- 403 Forbidden
    """

    async def _guard(request: Request) -> None:
        user = getattr(request.state, "user_session", None)
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        if "*" in user.permissions:
            return
        if permission not in user.permissions:
            raise HTTPException(
                status_code=403,
                detail=f"Permission '{permission}' required",
            )

    return Depends(_guard)


# ---------------------------------------------------------------------------
# Convenience aliases -- drop these straight into ``dependencies=[...]``
# ---------------------------------------------------------------------------

# Knowledge base
KnowledgeRead = require_permission("knowledge:read")
KnowledgeWrite = require_permission("knowledge:write")
KnowledgeDelete = require_permission("knowledge:delete")

# Service catalog
CatalogRead = require_permission("catalog:read")
CatalogWrite = require_permission("catalog:write")
CatalogDelete = require_permission("catalog:delete")

# Chat
ChatSend = require_permission("chat:send")

# Exports
ExportsCreate = require_permission("exports:create")
ExportsDownload = require_permission("exports:download")
ExportsDelete = require_permission("exports:delete")
ExportsTemplates = require_permission("exports:templates")

# Audit trail
AuditRead = require_permission("audit:read")

# Credentials vault
CredentialsRead = require_permission("credentials:read")
CredentialsWrite = require_permission("credentials:write")

# Jobs
JobsRead = require_permission("jobs:read")
JobsCancel = require_permission("jobs:cancel")

# Administration
AdminUsers = require_permission("admin:users")
AdminSettings = require_permission("admin:settings")
AdminRoles = require_permission("admin:roles")
AdminSSO = require_permission("admin:sso")
AdminLLM = require_permission("admin:llm")
AdminDashboard = require_permission("admin:dashboard")
