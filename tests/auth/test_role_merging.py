# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for local-to-SSO role merging in AuthMiddleware.

When a local admin switches to SSO login, their OIDC token may not contain
the local ``admin`` role.  The middleware should merge the local user's role
into the session so they don't lose access.
"""

from __future__ import annotations

import base64
import json
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from flydesk.auth.jwt_local import create_local_jwt
from flydesk.auth.middleware import AuthMiddleware
from flydesk.auth.models import UserSession

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_SECRET = "test-local-secret-key-for-role-merging"

SSO_CLAIMS: dict[str, Any] = {
    "sub": "sso-user-1",
    "email": "admin@corp.com",
    "name": "SSO Admin",
    "roles": ["viewer"],
    "permissions": [],
    "iss": "https://idp.corp.com",
    "exp": int(time.time()) + 3600,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _b64url(data: bytes) -> str:
    """Base64url-encode without padding (per JWT spec)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _make_oidc_token(claims: dict[str, Any] | None = None) -> str:
    """Build a fake OIDC JWT (RS256 + kid header).

    The middleware peeks at the unverified header to decide routing; actual
    validation is delegated to the mock token_decoder.
    """
    header = json.dumps({"alg": "RS256", "typ": "JWT", "kid": "test-key"}).encode()
    payload = json.dumps(claims or SSO_CLAIMS).encode()
    return f"{_b64url(header)}.{_b64url(payload)}.fake-sig"


OIDC_TOKEN = _make_oidc_token()


def _mock_sso_decoder(claims: dict[str, Any] | None = None):
    """Return a token_decoder that returns the given claims for any token."""
    effective = claims or SSO_CLAIMS

    def decoder(token: str) -> dict[str, Any]:
        return effective

    return decoder


def _make_local_user(
    *, email: str = "admin@corp.com", role: str = "admin", is_active: bool = True
) -> MagicMock:
    """Build a mock LocalUserRow."""
    user = MagicMock()
    user.email = email
    user.role = role
    user.is_active = is_active
    return user


def _make_local_user_repo(
    local_user: MagicMock | None = None,
) -> AsyncMock:
    """Build a mock LocalUserRepository."""
    repo = AsyncMock()
    repo.get_by_email = AsyncMock(return_value=local_user)
    return repo


def _build_app(
    *,
    token_decoder: Any = None,
    local_jwt_secret: str | None = None,
    local_user_repo: Any = None,
) -> FastAPI:
    """Create a minimal FastAPI app with AuthMiddleware for role-merging tests."""
    app = FastAPI()
    app.add_middleware(
        AuthMiddleware,
        token_decoder=token_decoder,
        local_jwt_secret=local_jwt_secret,
    )

    # Wire the local_user_repo on app.state (as the real server does)
    if local_user_repo is not None:
        app.state.local_user_repo = local_user_repo

    @app.get("/api/protected")
    async def protected(request: Request):
        session: UserSession = request.state.user_session
        return {
            "user_id": session.user_id,
            "email": session.email,
            "roles": session.roles,
        }

    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRoleMerging:
    """Tests for the local-to-SSO role merging feature."""

    async def test_sso_user_gets_local_admin_role_merged(self):
        """An SSO user whose email matches a local admin gets the admin role added."""
        local_user = _make_local_user(email="admin@corp.com", role="admin")
        repo = _make_local_user_repo(local_user)

        app = _build_app(
            token_decoder=_mock_sso_decoder(),
            local_user_repo=repo,
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/protected",
                headers={"Authorization": f"Bearer {OIDC_TOKEN}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "admin" in data["roles"]
        assert "viewer" in data["roles"]
        repo.get_by_email.assert_awaited_once_with("admin@corp.com")

    async def test_sso_user_no_local_match_unchanged(self):
        """An SSO user with no matching local account keeps original roles."""
        repo = _make_local_user_repo(None)  # No match

        app = _build_app(
            token_decoder=_mock_sso_decoder(),
            local_user_repo=repo,
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/protected",
                headers={"Authorization": f"Bearer {OIDC_TOKEN}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["roles"] == ["viewer"]

    async def test_local_jwt_skips_role_merging(self):
        """A local JWT (iss=flydesk-local) does NOT trigger role merging."""
        local_user = _make_local_user(email="local@example.com", role="admin")
        repo = _make_local_user_repo(local_user)

        token = create_local_jwt(
            user_id="local-1",
            email="local@example.com",
            display_name="Local Admin",
            roles=["admin"],
            secret_key=TEST_SECRET,
        )

        app = _build_app(
            local_jwt_secret=TEST_SECRET,
            local_user_repo=repo,
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/protected",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["roles"] == ["admin"]
        # The repo should NOT have been called for a local JWT
        repo.get_by_email.assert_not_awaited()

    async def test_sso_user_role_already_present_no_duplicate(self):
        """If the local role is already in the SSO roles, it is not duplicated."""
        # SSO token already has "admin" in roles
        claims_with_admin = {**SSO_CLAIMS, "roles": ["admin", "viewer"]}
        token = _make_oidc_token(claims_with_admin)

        local_user = _make_local_user(email="admin@corp.com", role="admin")
        repo = _make_local_user_repo(local_user)

        app = _build_app(
            token_decoder=_mock_sso_decoder(claims_with_admin),
            local_user_repo=repo,
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/protected",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        data = response.json()
        # Should still have exactly one "admin", not two
        assert data["roles"].count("admin") == 1
        assert data["roles"] == ["admin", "viewer"]

    async def test_inactive_local_user_not_merged(self):
        """An inactive local user's role is NOT merged into the SSO session."""
        local_user = _make_local_user(
            email="admin@corp.com", role="admin", is_active=False
        )
        repo = _make_local_user_repo(local_user)

        app = _build_app(
            token_decoder=_mock_sso_decoder(),
            local_user_repo=repo,
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/protected",
                headers={"Authorization": f"Bearer {OIDC_TOKEN}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["roles"] == ["viewer"]
        assert "admin" not in data["roles"]

    async def test_no_local_user_repo_on_app_state(self):
        """When local_user_repo is not on app.state, merging is gracefully skipped."""
        app = _build_app(
            token_decoder=_mock_sso_decoder(),
            # No local_user_repo set
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/protected",
                headers={"Authorization": f"Bearer {OIDC_TOKEN}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["roles"] == ["viewer"]
