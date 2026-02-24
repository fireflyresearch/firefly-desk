# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for JWT authentication middleware."""

from __future__ import annotations

import base64
import json
import time
from typing import Any

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from flydesk.auth.middleware import AuthMiddleware
from flydesk.auth.models import UserSession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_CLAIMS: dict[str, Any] = {
    "sub": "user-42",
    "email": "test@example.com",
    "name": "Test User",
    "roles": ["admin", "viewer"],
    "permissions": ["read", "write"],
    "tenant_id": "tenant-1",
    "exp": int(time.time()) + 3600,
}


def _b64url(data: bytes) -> str:
    """Base64url-encode without padding (per JWT spec)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _make_fake_jwt(name: str) -> str:
    """Build a fake JWT with RS256+kid header so the middleware routes it to token_decoder.

    The ``name`` is embedded in the payload so the mock decoder can identify it.
    The token has a valid JWT structure (three dot-separated base64url segments)
    but the signature is fake -- the mock decoder never verifies it.
    """
    header = json.dumps({"alg": "RS256", "typ": "JWT", "kid": "test-key"}).encode()
    payload = json.dumps({"_test_name": name}).encode()
    return f"{_b64url(header)}.{_b64url(payload)}.fake-sig"


# Pre-built fake JWTs for the mock decoder
GOOD_TOKEN = _make_fake_jwt("good-token")
BAD_TOKEN = _make_fake_jwt("bad-token")
NESTED_TOKEN = _make_fake_jwt("nested-token")


def _mock_decoder(token: str) -> dict[str, Any]:
    """Return valid claims for the good token, raise for anything else."""
    if token == GOOD_TOKEN:
        return VALID_CLAIMS
    raise ValueError("bad token")


def _build_app(
    *,
    roles_claim: str = "roles",
    permissions_claim: str = "permissions",
) -> FastAPI:
    """Create a minimal FastAPI app with AuthMiddleware for testing."""
    app = FastAPI()
    app.add_middleware(
        AuthMiddleware,
        roles_claim=roles_claim,
        permissions_claim=permissions_claim,
        token_decoder=_mock_decoder,
    )

    @app.get("/api/health")
    async def health():
        return {"status": "healthy"}

    @app.get("/api/protected")
    async def protected(request: Request):
        session: UserSession = request.state.user_session
        return {
            "user_id": session.user_id,
            "email": session.email,
            "display_name": session.display_name,
            "roles": session.roles,
            "permissions": session.permissions,
            "tenant_id": session.tenant_id,
        }

    return app


@pytest.fixture
async def client():
    """AsyncClient wired to a test FastAPI app."""
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def nested_claims_client():
    """AsyncClient wired to a test app using dot-notation claim paths."""
    app = _build_app(
        roles_claim="realm_access.roles",
        permissions_claim="resource_access.permissions",
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAuthMiddleware:
    async def test_public_path_bypasses_auth(self, client: AsyncClient):
        """Health endpoint does not require an Authorization header."""
        response = await client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    async def test_missing_auth_header_returns_401(self, client: AsyncClient):
        """A request with no Authorization header returns 401."""
        response = await client.get("/api/protected")
        assert response.status_code == 401
        assert "Missing or invalid" in response.json()["detail"]

    async def test_invalid_token_returns_401(self, client: AsyncClient):
        """A request with a bad token returns 401."""
        response = await client.get(
            "/api/protected",
            headers={"Authorization": f"Bearer {BAD_TOKEN}"},
        )
        assert response.status_code == 401
        assert "Invalid or expired" in response.json()["detail"]

    async def test_valid_token_creates_user_session(self, client: AsyncClient):
        """A valid token produces a UserSession available on request.state."""
        response = await client.get(
            "/api/protected",
            headers={"Authorization": f"Bearer {GOOD_TOKEN}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user-42"
        assert data["email"] == "test@example.com"
        assert data["display_name"] == "Test User"
        assert data["tenant_id"] == "tenant-1"

    async def test_roles_extracted_from_claims(self, client: AsyncClient):
        """Roles are pulled from the configurable claim key."""
        response = await client.get(
            "/api/protected",
            headers={"Authorization": f"Bearer {GOOD_TOKEN}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["roles"] == ["admin", "viewer"]
        assert data["permissions"] == ["read", "write"]

    async def test_dot_notation_claim_extraction(self, nested_claims_client: AsyncClient):
        """Dot-notation claim paths like 'realm_access.roles' are resolved."""
        # The mock decoder returns flat claims, so we need a decoder that
        # returns nested claims for this test.
        nested_claims = {
            **VALID_CLAIMS,
            "realm_access": {"roles": ["realm-admin"]},
            "resource_access": {"permissions": ["res:read"]},
        }

        def nested_decoder(token: str) -> dict[str, Any]:
            if token == NESTED_TOKEN:
                return nested_claims
            raise ValueError("bad token")

        # Build a dedicated app with the nested decoder
        app = FastAPI()
        app.add_middleware(
            AuthMiddleware,
            roles_claim="realm_access.roles",
            permissions_claim="resource_access.permissions",
            token_decoder=nested_decoder,
        )

        @app.get("/api/protected")
        async def protected(request: Request):
            session: UserSession = request.state.user_session
            return {"roles": session.roles, "permissions": session.permissions}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/protected",
                headers={"Authorization": f"Bearer {NESTED_TOKEN}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["roles"] == ["realm-admin"]
        assert data["permissions"] == ["res:read"]
