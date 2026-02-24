# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for dual-mode JWT decoding in AuthMiddleware.

Validates that the middleware correctly routes tokens based on their
JWT header:

* **HS256 + no ``kid``** -> local JWT path (``decode_local_jwt``)
* **RS256/ES256 + ``kid``** -> OIDC path (``oidc_client.validate_token``)
* Fallback to ``token_decoder`` when no OIDC client is configured
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock

import base64
import json

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from flydesk.auth.jwt_local import create_local_jwt
from flydesk.auth.middleware import AuthMiddleware
from flydesk.auth.models import UserSession

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_SECRET = "test-local-secret-key-for-unit-tests"

VALID_LOCAL_CLAIMS: dict[str, Any] = {
    "sub": "local-user-1",
    "email": "local@example.com",
    "name": "Local User",
    "roles": ["admin", "agent"],
}

VALID_OIDC_CLAIMS: dict[str, Any] = {
    "sub": "oidc-user-1",
    "email": "oidc@example.com",
    "name": "OIDC User",
    "roles": ["viewer"],
    "permissions": ["read"],
    "exp": int(time.time()) + 3600,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_local_token() -> str:
    """Create a real HS256 local JWT for testing."""
    return create_local_jwt(
        user_id=VALID_LOCAL_CLAIMS["sub"],
        email=VALID_LOCAL_CLAIMS["email"],
        display_name=VALID_LOCAL_CLAIMS["name"],
        roles=VALID_LOCAL_CLAIMS["roles"],
        secret_key=TEST_SECRET,
    )


def _b64url(data: bytes) -> str:
    """Base64url-encode without padding (per JWT spec)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _make_oidc_like_token() -> str:
    """Create a token whose header says RS256 + kid.

    The middleware only peeks at the *unverified* header to decide routing;
    actual validation is delegated to the OIDC client mock or token_decoder.
    We construct the JWT manually to avoid needing a real RSA key.
    """
    header = json.dumps({"alg": "RS256", "typ": "JWT", "kid": "oidc-key-1"}).encode()
    payload = json.dumps(VALID_OIDC_CLAIMS).encode()
    # Fake signature -- the mock decoder never verifies it
    return f"{_b64url(header)}.{_b64url(payload)}.fake-signature"


def _build_local_app(*, local_jwt_secret: str | None = TEST_SECRET) -> FastAPI:
    """FastAPI app with AuthMiddleware configured for local JWTs."""
    app = FastAPI()
    app.add_middleware(
        AuthMiddleware,
        local_jwt_secret=local_jwt_secret,
    )

    @app.get("/api/health")
    async def health():
        return {"status": "healthy"}

    @app.get("/api/auth/login")
    async def login():
        return {"status": "login_page"}

    @app.get("/api/setup/create-admin")
    async def create_admin():
        return {"status": "setup_page"}

    @app.get("/api/protected")
    async def protected(request: Request):
        session: UserSession = request.state.user_session
        return {
            "user_id": session.user_id,
            "email": session.email,
            "display_name": session.display_name,
            "roles": session.roles,
        }

    return app


def _build_oidc_app(oidc_client: Any) -> FastAPI:
    """FastAPI app with AuthMiddleware configured for OIDC."""
    app = FastAPI()
    app.add_middleware(
        AuthMiddleware,
        oidc_client=oidc_client,
    )

    @app.get("/api/protected")
    async def protected(request: Request):
        session: UserSession = request.state.user_session
        return {
            "user_id": session.user_id,
            "email": session.email,
        }

    return app


def _build_fallback_app(decoder: Any) -> FastAPI:
    """FastAPI app with AuthMiddleware configured with a token_decoder fallback."""
    app = FastAPI()
    app.add_middleware(
        AuthMiddleware,
        token_decoder=decoder,
    )

    @app.get("/api/protected")
    async def protected(request: Request):
        session: UserSession = request.state.user_session
        return {
            "user_id": session.user_id,
            "email": session.email,
        }

    return app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def local_client():
    """AsyncClient wired to a local-JWT-enabled app."""
    app = _build_local_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def local_client_no_secret():
    """AsyncClient wired to an app without a local_jwt_secret."""
    app = _build_local_app(local_jwt_secret=None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLocalJwtPath:
    """Tests for the HS256 local JWT decoding path."""

    async def test_local_jwt_decoded_correctly(self, local_client: AsyncClient):
        """A valid HS256 local JWT is decoded and produces a UserSession."""
        token = _make_local_token()
        response = await local_client.get(
            "/api/protected",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "local-user-1"
        assert data["email"] == "local@example.com"
        assert data["display_name"] == "Local User"
        assert data["roles"] == ["admin", "agent"]

    async def test_local_jwt_wrong_secret_returns_401(self, local_client: AsyncClient):
        """A local JWT signed with a different secret is rejected."""
        bad_token = create_local_jwt(
            user_id="user",
            email="u@example.com",
            display_name="U",
            roles=[],
            secret_key="wrong-secret",
        )
        response = await local_client.get(
            "/api/protected",
            headers={"Authorization": f"Bearer {bad_token}"},
        )
        assert response.status_code == 401

    async def test_hs256_without_secret_returns_401(
        self, local_client_no_secret: AsyncClient
    ):
        """HS256 token when local_jwt_secret is not configured returns 401."""
        token = _make_local_token()
        response = await local_client_no_secret.get(
            "/api/protected",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
        assert "Invalid or expired" in response.json()["detail"]

    async def test_garbage_token_returns_401(self, local_client: AsyncClient):
        """A non-JWT string returns 401 (invalid header)."""
        response = await local_client.get(
            "/api/protected",
            headers={"Authorization": "Bearer not-a-jwt"},
        )
        assert response.status_code == 401


class TestOidcJwtPath:
    """Tests for the OIDC token routing path."""

    async def test_oidc_token_routed_to_oidc_client(self):
        """A token with RS256 + kid is routed to the OIDC client."""
        mock_oidc = AsyncMock()
        mock_oidc.validate_token = AsyncMock(return_value=VALID_OIDC_CLAIMS)

        app = _build_oidc_app(mock_oidc)
        transport = ASGITransport(app=app)
        token = _make_oidc_like_token()

        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/protected",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "oidc-user-1"
        assert data["email"] == "oidc@example.com"
        mock_oidc.validate_token.assert_awaited_once_with(token)


class TestTokenDecoderFallback:
    """Tests for the legacy token_decoder fallback path."""

    async def test_fallback_to_token_decoder(self):
        """Non-local tokens fall back to token_decoder when no OIDC client."""
        token = _make_oidc_like_token()

        def mock_decoder(t: str) -> dict[str, Any]:
            return VALID_OIDC_CLAIMS

        app = _build_fallback_app(mock_decoder)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/protected",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "oidc-user-1"

    async def test_no_decoder_configured_returns_401(self):
        """Non-local token with no OIDC client and no decoder returns 401."""
        token = _make_oidc_like_token()

        app = FastAPI()
        app.add_middleware(AuthMiddleware)

        @app.get("/api/protected")
        async def protected(request: Request):
            return {"ok": True}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/protected",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 401


class TestPublicPaths:
    """Tests for the newly added public path prefixes."""

    async def test_login_path_is_public(self, local_client: AsyncClient):
        """/api/auth/login does not require authentication."""
        response = await local_client.get("/api/auth/login")
        assert response.status_code == 200
        assert response.json()["status"] == "login_page"

    async def test_create_admin_path_is_public(self, local_client: AsyncClient):
        """/api/setup/create-admin does not require authentication."""
        response = await local_client.get("/api/setup/create-admin")
        assert response.status_code == 200
        assert response.json()["status"] == "setup_page"

    async def test_login_subpath_is_public(self, local_client: AsyncClient):
        """/api/auth/login/... sub-paths are also public (prefix match)."""
        # This path doesn't have a route, so FastAPI returns 404 (not 401).
        response = await local_client.get("/api/auth/login/some-subpath")
        assert response.status_code != 401
