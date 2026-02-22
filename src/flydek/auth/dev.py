# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Development-only auth middleware that injects a synthetic admin session."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from flydek.auth.models import UserSession


def _build_dev_user() -> UserSession:
    """Build a synthetic admin session from environment variables.

    Reads the following env vars (with sensible defaults):

    * ``FLYDEK_DEV_USER_NAME`` -- display name (default: ``"Dev Admin"``)
    * ``FLYDEK_DEV_USER_EMAIL`` -- email address (default: ``"admin@localhost"``)
    * ``FLYDEK_DEV_USER_ROLES`` -- comma-separated roles (default: ``"admin,operator"``)
    * ``FLYDEK_DEV_USER_PICTURE`` -- avatar / picture URL (default: ``None``)
    * ``FLYDEK_DEV_USER_DEPARTMENT`` -- department (default: ``None``)
    * ``FLYDEK_DEV_USER_TITLE`` -- job title (default: ``None``)
    """
    display_name = os.environ.get("FLYDEK_DEV_USER_NAME", "Dev Admin")
    email = os.environ.get("FLYDEK_DEV_USER_EMAIL", "admin@localhost")
    roles = os.environ.get("FLYDEK_DEV_USER_ROLES", "admin,operator").split(",")
    picture_url = os.environ.get("FLYDEK_DEV_USER_PICTURE") or None
    department = os.environ.get("FLYDEK_DEV_USER_DEPARTMENT") or None
    title = os.environ.get("FLYDEK_DEV_USER_TITLE") or None

    return UserSession(
        user_id="dev-user-001",
        email=email,
        display_name=display_name,
        roles=roles,
        permissions=["*"],
        tenant_id="dev-tenant",
        picture_url=picture_url,
        department=department,
        title=title,
        session_id=str(uuid.uuid4()),
        token_expires_at=datetime(2099, 12, 31, tzinfo=timezone.utc),
        raw_claims={
            "sub": "dev-user-001",
            "name": display_name,
            "email": email,
        },
    )


class DevAuthMiddleware(BaseHTTPMiddleware):
    """Bypass authentication in dev mode by injecting a synthetic admin user.

    The dev user is built once at ``__init__`` time (reading env vars) and
    reused for every request, avoiding repeated ``os.environ`` lookups.

    If a ``user_session`` is already set (e.g. by a test fixture), it is
    left untouched so that tests can override the dev user.
    """

    def __init__(self, app: Any, **kwargs: Any) -> None:  # noqa: ANN401
        super().__init__(app, **kwargs)
        self._dev_user = _build_dev_user()

    async def dispatch(self, request: Request, call_next) -> Response:  # noqa: ANN001
        if not getattr(request.state, "user_session", None):
            request.state.user_session = self._dev_user
        return await call_next(request)
