# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for dynamic OIDC provider resolution in AuthMiddleware.

Validates that the middleware can resolve DB-managed OIDC providers
by peeking at the ``iss`` claim of an incoming JWT, creating/caching
an ``OIDCClient`` for that provider, and falling back to the static
client when no match is found.
"""

from __future__ import annotations

import base64
import json
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from flydesk.auth.middleware import AuthMiddleware
from flydesk.auth.models import UserSession

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ISSUER_URL = "https://auth.example.com/realms/test"

VALID_OIDC_CLAIMS: dict[str, Any] = {
    "sub": "dynamic-user-1",
    "email": "dynamic@example.com",
    "name": "Dynamic User",
    "iss": ISSUER_URL,
    "roles": ["editor"],
    "permissions": ["write"],
    "exp": int(time.time()) + 3600,
}

STATIC_OIDC_CLAIMS: dict[str, Any] = {
    "sub": "static-user-1",
    "email": "static@example.com",
    "name": "Static User",
    "iss": "https://static-issuer.example.com",
    "roles": ["viewer"],
    "permissions": ["read"],
    "exp": int(time.time()) + 3600,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _b64url(data: bytes) -> str:
    """Base64url-encode without padding (per JWT spec)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _make_oidc_token(claims: dict[str, Any] | None = None) -> str:
    """Create a token whose header says RS256 + kid.

    The middleware peeks at the unverified header and claims to decide
    routing.  Actual validation is delegated to mock OIDC clients.
    """
    header = json.dumps({"alg": "RS256", "typ": "JWT", "kid": "test-kid-1"}).encode()
    payload = json.dumps(claims or VALID_OIDC_CLAIMS).encode()
    return f"{_b64url(header)}.{_b64url(payload)}.fake-signature"


def _make_provider_row(
    *,
    issuer_url: str = ISSUER_URL,
    provider_type: str = "keycloak",
    client_id: str = "db-client-id",
    is_active: bool = True,
    client_secret_encrypted: str | None = "encrypted-secret",
) -> MagicMock:
    """Create a mock OIDCProviderRow."""
    row = MagicMock()
    row.issuer_url = issuer_url
    row.provider_type = provider_type
    row.client_id = client_id
    row.is_active = is_active
    row.client_secret_encrypted = client_secret_encrypted
    return row


def _make_oidc_repo(
    providers: list[Any] | None = None,
    decrypted_secret: str = "decrypted-secret",
) -> AsyncMock:
    """Create a mock OIDCProviderRepository."""
    repo = AsyncMock()
    repo.list_providers = AsyncMock(return_value=providers or [])
    repo.decrypt_secret = MagicMock(return_value=decrypted_secret)
    return repo


def _build_app(
    *,
    oidc_client: Any = None,
    oidc_repo: Any = None,
    token_decoder: Any = None,
    provider_profile: Any = None,
) -> FastAPI:
    """FastAPI app with AuthMiddleware configured for dynamic resolution tests."""
    app = FastAPI()
    app.add_middleware(
        AuthMiddleware,
        oidc_client=oidc_client,
        oidc_repo=oidc_repo,
        token_decoder=token_decoder,
        provider_profile=provider_profile,
    )

    @app.get("/api/protected")
    async def protected(request: Request):
        session: UserSession = request.state.user_session
        return {
            "user_id": session.user_id,
            "email": session.email,
            "display_name": session.display_name,
            "roles": session.roles,
            "permissions": session.permissions,
        }

    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDynamicOIDCResolution:
    """Tests for dynamic OIDC provider resolution from DB."""

    async def test_token_resolved_via_db_provider(self):
        """OIDC token with issuer matching a DB provider is resolved dynamically."""
        provider_row = _make_provider_row()
        oidc_repo = _make_oidc_repo(providers=[provider_row])

        # The dynamically created OIDCClient will have validate_token called.
        # We patch OIDCClient so we control what it returns.
        mock_client_instance = AsyncMock()
        mock_client_instance.validate_token = AsyncMock(return_value=VALID_OIDC_CLAIMS)

        with patch(
            "flydesk.auth.oidc.OIDCClient",
            return_value=mock_client_instance,
        ) as mock_cls:
            app = _build_app(oidc_repo=oidc_repo)
            transport = ASGITransport(app=app)
            token = _make_oidc_token()

            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get(
                    "/api/protected",
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == "dynamic-user-1"
            assert data["email"] == "dynamic@example.com"

            # Verify OIDCClient was constructed with DB provider details
            mock_cls.assert_called_once_with(
                issuer_url=ISSUER_URL,
                client_id="db-client-id",
                client_secret="decrypted-secret",
            )
            mock_client_instance.validate_token.assert_awaited_once_with(token)
            oidc_repo.list_providers.assert_awaited_once()

    async def test_cache_hit_no_db_query(self):
        """Second request with same issuer uses cache, no DB query."""
        provider_row = _make_provider_row()
        oidc_repo = _make_oidc_repo(providers=[provider_row])

        mock_client_instance = AsyncMock()
        mock_client_instance.validate_token = AsyncMock(return_value=VALID_OIDC_CLAIMS)

        with patch(
            "flydesk.auth.oidc.OIDCClient",
            return_value=mock_client_instance,
        ):
            app = _build_app(oidc_repo=oidc_repo)
            transport = ASGITransport(app=app)
            token = _make_oidc_token()

            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                # First request -- populates cache
                resp1 = await ac.get(
                    "/api/protected",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert resp1.status_code == 200

                # Reset call count to verify second request doesn't query DB
                oidc_repo.list_providers.reset_mock()

                # Second request -- should use cache
                resp2 = await ac.get(
                    "/api/protected",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert resp2.status_code == 200

            # Cache hit: no DB query on second request
            oidc_repo.list_providers.assert_not_awaited()

    async def test_cache_expired_re_queries_db(self):
        """Expired cache entry causes re-query of DB."""
        provider_row = _make_provider_row()
        oidc_repo = _make_oidc_repo(providers=[provider_row])

        mock_client_instance = AsyncMock()
        mock_client_instance.validate_token = AsyncMock(return_value=VALID_OIDC_CLAIMS)

        with patch(
            "flydesk.auth.oidc.OIDCClient",
            return_value=mock_client_instance,
        ):
            app = _build_app(oidc_repo=oidc_repo)
            transport = ASGITransport(app=app)
            token = _make_oidc_token()

            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                # First request -- populates cache
                resp1 = await ac.get(
                    "/api/protected",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert resp1.status_code == 200

                # Manually expire the cache by backdating the timestamp
                mw = app.middleware_stack
                # Walk the middleware stack to find AuthMiddleware
                auth_mw = _find_auth_middleware(app)
                assert auth_mw is not None, "Could not find AuthMiddleware in stack"

                # Backdate cache entry by more than the TTL
                issuer = ISSUER_URL
                cached = auth_mw._provider_cache.get(issuer)
                if cached:
                    auth_mw._provider_cache[issuer] = (
                        cached[0],
                        cached[1],
                        time.time() - 600,  # 10 minutes ago
                    )

                oidc_repo.list_providers.reset_mock()

                # Third request -- cache expired, should re-query DB
                resp3 = await ac.get(
                    "/api/protected",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert resp3.status_code == 200

            # DB was queried again after cache expiry
            oidc_repo.list_providers.assert_awaited_once()

    async def test_no_matching_provider_falls_back_to_static(self):
        """No matching DB provider falls back to static oidc_client."""
        # DB has a provider with different issuer
        provider_row = _make_provider_row(issuer_url="https://other-issuer.example.com")
        oidc_repo = _make_oidc_repo(providers=[provider_row])

        # Static OIDC client
        mock_static = AsyncMock()
        mock_static.validate_token = AsyncMock(return_value=STATIC_OIDC_CLAIMS)

        app = _build_app(oidc_client=mock_static, oidc_repo=oidc_repo)
        transport = ASGITransport(app=app)
        token = _make_oidc_token()  # issuer is ISSUER_URL, not matching DB

        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/protected",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        data = response.json()
        # Should get static client's claims
        assert data["user_id"] == "static-user-1"
        mock_static.validate_token.assert_awaited_once_with(token)

    async def test_no_oidc_repo_and_no_static_falls_back_to_decoder(self):
        """No oidc_repo and no static client falls back to token_decoder."""
        token = _make_oidc_token()

        def mock_decoder(t: str) -> dict[str, Any]:
            return VALID_OIDC_CLAIMS

        app = _build_app(token_decoder=mock_decoder)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/protected",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "dynamic-user-1"

    async def test_dynamic_provider_profile_used_for_claim_extraction(self):
        """Dynamically resolved profile is used for provider-specific claim extraction."""
        # Create a keycloak-style provider (has specific claim mappings)
        provider_row = _make_provider_row(provider_type="keycloak")
        oidc_repo = _make_oidc_repo(providers=[provider_row])

        # Claims with Keycloak-style nested roles
        keycloak_claims = {
            **VALID_OIDC_CLAIMS,
            "realm_access": {"roles": ["kc-admin", "kc-user"]},
            "picture": "https://example.com/photo.jpg",
        }

        mock_client_instance = AsyncMock()
        mock_client_instance.validate_token = AsyncMock(return_value=keycloak_claims)

        with patch(
            "flydesk.auth.oidc.OIDCClient",
            return_value=mock_client_instance,
        ):
            app = _build_app(oidc_repo=oidc_repo)

            @app.get("/api/session-detail")
            async def session_detail(request: Request):
                session: UserSession = request.state.user_session
                return {
                    "roles": session.roles,
                    "picture_url": session.picture_url,
                }

            transport = ASGITransport(app=app)
            token = _make_oidc_token(keycloak_claims)

            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get(
                    "/api/session-detail",
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 200
            data = response.json()
            # Keycloak profile extracts roles from realm_access.roles
            assert data["roles"] == ["kc-admin", "kc-user"]
            assert data["picture_url"] == "https://example.com/photo.jpg"

    async def test_inactive_provider_not_resolved(self):
        """Inactive DB provider is skipped during resolution."""
        provider_row = _make_provider_row(is_active=False)
        oidc_repo = _make_oidc_repo(providers=[provider_row])

        # Static OIDC client as fallback
        mock_static = AsyncMock()
        mock_static.validate_token = AsyncMock(return_value=STATIC_OIDC_CLAIMS)

        app = _build_app(oidc_client=mock_static, oidc_repo=oidc_repo)
        transport = ASGITransport(app=app)
        token = _make_oidc_token()

        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/protected",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        data = response.json()
        # Falls through to static because DB provider is inactive
        assert data["user_id"] == "static-user-1"

    async def test_issuer_trailing_slash_normalization(self):
        """Issuer comparison normalizes trailing slashes."""
        # DB provider has trailing slash, token does not
        provider_row = _make_provider_row(issuer_url=ISSUER_URL + "/")
        oidc_repo = _make_oidc_repo(providers=[provider_row])

        mock_client_instance = AsyncMock()
        mock_client_instance.validate_token = AsyncMock(return_value=VALID_OIDC_CLAIMS)

        with patch(
            "flydesk.auth.oidc.OIDCClient",
            return_value=mock_client_instance,
        ):
            app = _build_app(oidc_repo=oidc_repo)
            transport = ASGITransport(app=app)
            token = _make_oidc_token()  # issuer has no trailing slash

            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get(
                    "/api/protected",
                    headers={"Authorization": f"Bearer {token}"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == "dynamic-user-1"


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _find_auth_middleware(app: FastAPI) -> AuthMiddleware | None:
    """Walk the ASGI middleware stack to find the AuthMiddleware instance."""
    current = app.middleware_stack
    while current is not None:
        if isinstance(current, AuthMiddleware):
            return current
        current = getattr(current, "app", None)
    return None
