# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the AuthResolver credential-to-header resolution."""

from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from flydesk.catalog.enums import AuthType
from flydesk.catalog.models import AuthConfig, Credential, ExternalSystem
from flydesk.tools.auth_resolver import AuthResolver, _TokenCache


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_system(
    auth_type: AuthType,
    credential_id: str = "cred-1",
    auth_headers: dict[str, str] | None = None,
    token_url: str | None = None,
    scopes: list[str] | None = None,
) -> ExternalSystem:
    return ExternalSystem(
        id="sys-1",
        name="Test System",
        description="A test system",
        base_url="https://api.example.com",
        auth_config=AuthConfig(
            auth_type=auth_type,
            credential_id=credential_id,
            auth_headers=auth_headers,
            token_url=token_url,
            scopes=scopes,
        ),
    )


def _make_credential(
    credential_id: str = "cred-1",
    encrypted_value: str = "secret-token-123",
) -> Credential:
    return Credential(
        id=credential_id,
        system_id="sys-1",
        name="Test Credential",
        encrypted_value=encrypted_value,
        credential_type="token",
    )


@pytest.fixture
def credential_store() -> MagicMock:
    mock = MagicMock()
    mock.get_credential = AsyncMock(return_value=_make_credential())
    return mock


@pytest.fixture
def http_client() -> AsyncMock:
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def resolver(credential_store: MagicMock) -> AuthResolver:
    return AuthResolver(credential_store)


@pytest.fixture
def resolver_with_http(credential_store: MagicMock, http_client: AsyncMock) -> AuthResolver:
    return AuthResolver(credential_store, http_client=http_client)


# ---------------------------------------------------------------------------
# Token Cache
# ---------------------------------------------------------------------------


class TestTokenCache:
    def test_get_returns_none_for_missing_key(self):
        cache = _TokenCache()
        assert cache.get("unknown") is None

    def test_put_and_get(self):
        cache = _TokenCache()
        cache.put("k1", "tok-abc", 3600)
        assert cache.get("k1") == "tok-abc"

    def test_expired_token_returns_none(self):
        cache = _TokenCache()
        # Put with 0 seconds expiry → already expired (within buffer)
        cache.put("k1", "tok-old", 0)
        assert cache.get("k1") is None

    def test_near_expiry_returns_none(self):
        cache = _TokenCache()
        # Put a token that expires in 30 seconds — within the 60s buffer
        cache.put("k1", "tok-soon", 30)
        assert cache.get("k1") is None

    def test_overwrite_existing_key(self):
        cache = _TokenCache()
        cache.put("k1", "first", 3600)
        cache.put("k1", "second", 3600)
        assert cache.get("k1") == "second"


# ---------------------------------------------------------------------------
# Bearer Auth
# ---------------------------------------------------------------------------


class TestBearerAuth:
    async def test_returns_bearer_header(self, resolver: AuthResolver):
        system = _make_system(AuthType.BEARER)
        headers = await resolver.resolve_headers(system)

        assert headers == {"Authorization": "Bearer secret-token-123"}

    async def test_uses_correct_credential_id(
        self, resolver: AuthResolver, credential_store
    ):
        system = _make_system(AuthType.BEARER, credential_id="my-cred")
        await resolver.resolve_headers(system)

        credential_store.get_credential.assert_awaited_once_with("my-cred")


# ---------------------------------------------------------------------------
# API Key Auth
# ---------------------------------------------------------------------------


class TestApiKeyAuth:
    async def test_returns_default_header_name(self, resolver: AuthResolver):
        system = _make_system(AuthType.API_KEY)
        headers = await resolver.resolve_headers(system)

        assert headers == {"X-Api-Key": "secret-token-123"}

    async def test_uses_custom_header_name(self, resolver: AuthResolver):
        system = _make_system(
            AuthType.API_KEY,
            auth_headers={"X-Custom-Key": ""},
        )
        headers = await resolver.resolve_headers(system)

        assert "X-Custom-Key" in headers
        assert headers["X-Custom-Key"] == "secret-token-123"

    async def test_uses_first_header_from_auth_headers(self, resolver: AuthResolver):
        system = _make_system(
            AuthType.API_KEY,
            auth_headers={"Api-Token": "", "Backup-Token": ""},
        )
        headers = await resolver.resolve_headers(system)

        assert "Api-Token" in headers


# ---------------------------------------------------------------------------
# Basic Auth
# ---------------------------------------------------------------------------


class TestBasicAuth:
    async def test_returns_basic_header(self, resolver: AuthResolver, credential_store):
        credential_store.get_credential.return_value = _make_credential(
            encrypted_value="dXNlcjpwYXNzd29yZA==",
        )
        system = _make_system(AuthType.BASIC)
        headers = await resolver.resolve_headers(system)

        assert headers == {"Authorization": "Basic dXNlcjpwYXNzd29yZA=="}


# ---------------------------------------------------------------------------
# OAuth2 Auth
# ---------------------------------------------------------------------------


class TestOAuth2Auth:
    async def test_fallback_uses_stored_token_as_bearer(self, resolver: AuthResolver):
        """When credential is a plain token (not JSON), use it as bearer."""
        system = _make_system(AuthType.OAUTH2)
        headers = await resolver.resolve_headers(system)

        assert headers == {"Authorization": "Bearer secret-token-123"}

    async def test_fallback_when_no_token_url(self, resolver: AuthResolver, credential_store):
        """JSON creds but no token_url → fallback to stored value."""
        creds_json = json.dumps({"client_id": "cid", "client_secret": "csec"})
        credential_store.get_credential.return_value = _make_credential(
            encrypted_value=creds_json,
        )
        system = _make_system(AuthType.OAUTH2)  # no token_url
        headers = await resolver.resolve_headers(system)

        assert headers == {"Authorization": f"Bearer {creds_json}"}

    async def test_client_credentials_exchange(
        self, resolver_with_http: AuthResolver, credential_store, http_client
    ):
        """Full OAuth2 client credentials grant with token exchange."""
        creds_json = json.dumps({"client_id": "my-id", "client_secret": "my-secret"})
        credential_store.get_credential.return_value = _make_credential(
            encrypted_value=creds_json,
        )

        # Mock HTTP response from token endpoint
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "fresh-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()
        http_client.post = AsyncMock(return_value=mock_response)

        system = _make_system(
            AuthType.OAUTH2,
            token_url="https://auth.example.com/token",
            scopes=["read", "write"],
        )
        headers = await resolver_with_http.resolve_headers(system)

        assert headers == {"Authorization": "Bearer fresh-access-token"}

        # Verify the POST was made with correct params
        http_client.post.assert_awaited_once()
        call_kwargs = http_client.post.call_args
        assert call_kwargs.args[0] == "https://auth.example.com/token"
        assert call_kwargs.kwargs["data"]["grant_type"] == "client_credentials"
        assert call_kwargs.kwargs["data"]["client_id"] == "my-id"
        assert call_kwargs.kwargs["data"]["client_secret"] == "my-secret"
        assert call_kwargs.kwargs["data"]["scope"] == "read write"

    async def test_token_is_cached(
        self, resolver_with_http: AuthResolver, credential_store, http_client
    ):
        """Second call should use cached token, not make another HTTP request."""
        creds_json = json.dumps({"client_id": "cid", "client_secret": "csec"})
        credential_store.get_credential.return_value = _make_credential(
            encrypted_value=creds_json,
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "cached-token",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()
        http_client.post = AsyncMock(return_value=mock_response)

        system = _make_system(
            AuthType.OAUTH2,
            token_url="https://auth.example.com/token",
        )

        # First call → HTTP request
        h1 = await resolver_with_http.resolve_headers(system)
        assert h1 == {"Authorization": "Bearer cached-token"}
        assert http_client.post.await_count == 1

        # Second call → cached, no new HTTP request
        h2 = await resolver_with_http.resolve_headers(system)
        assert h2 == {"Authorization": "Bearer cached-token"}
        assert http_client.post.await_count == 1  # Still 1

    async def test_exchange_failure_falls_back_to_stored_token(
        self, resolver_with_http: AuthResolver, credential_store, http_client
    ):
        """If token exchange fails, fall back to stored credential as bearer."""
        creds_json = json.dumps({"client_id": "cid", "client_secret": "csec"})
        credential_store.get_credential.return_value = _make_credential(
            encrypted_value=creds_json,
        )

        # Simulate HTTP error
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        http_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "401", request=MagicMock(), response=mock_response,
            ),
        )

        system = _make_system(
            AuthType.OAUTH2,
            token_url="https://auth.example.com/token",
        )
        headers = await resolver_with_http.resolve_headers(system)

        # Falls back to using the stored JSON string as a bearer token
        assert headers == {"Authorization": f"Bearer {creds_json}"}

    async def test_no_http_client_falls_back(
        self, resolver: AuthResolver, credential_store
    ):
        """OAuth2 with no http_client configured falls back to stored token."""
        creds_json = json.dumps({"client_id": "cid", "client_secret": "csec"})
        credential_store.get_credential.return_value = _make_credential(
            encrypted_value=creds_json,
        )

        system = _make_system(
            AuthType.OAUTH2,
            token_url="https://auth.example.com/token",
        )
        headers = await resolver.resolve_headers(system)

        assert headers == {"Authorization": f"Bearer {creds_json}"}

    async def test_exchange_missing_access_token_falls_back(
        self, resolver_with_http: AuthResolver, credential_store, http_client
    ):
        """If token endpoint response has no access_token, fall back."""
        creds_json = json.dumps({"client_id": "cid", "client_secret": "csec"})
        credential_store.get_credential.return_value = _make_credential(
            encrypted_value=creds_json,
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {"error": "invalid_grant"}
        mock_response.raise_for_status = MagicMock()
        http_client.post = AsyncMock(return_value=mock_response)

        system = _make_system(
            AuthType.OAUTH2,
            token_url="https://auth.example.com/token",
        )
        headers = await resolver_with_http.resolve_headers(system)

        assert headers == {"Authorization": f"Bearer {creds_json}"}


# ---------------------------------------------------------------------------
# Mutual TLS
# ---------------------------------------------------------------------------


class TestMutualTlsAuth:
    async def test_returns_empty_headers_without_auth_headers(self, resolver: AuthResolver):
        system = _make_system(AuthType.MUTUAL_TLS)
        headers = await resolver.resolve_headers(system)

        assert headers == {}

    async def test_returns_custom_auth_headers(self, resolver: AuthResolver):
        system = _make_system(
            AuthType.MUTUAL_TLS,
            auth_headers={"X-Client-Cert-DN": "CN=myapp"},
        )
        headers = await resolver.resolve_headers(system)

        assert headers == {"X-Client-Cert-DN": "CN=myapp"}


# ---------------------------------------------------------------------------
# Missing credential
# ---------------------------------------------------------------------------


class TestMissingCredential:
    async def test_raises_on_missing_credential(
        self, resolver: AuthResolver, credential_store
    ):
        credential_store.get_credential.return_value = None
        system = _make_system(AuthType.BEARER, credential_id="nonexistent")

        with pytest.raises(ValueError, match="not found"):
            await resolver.resolve_headers(system)
