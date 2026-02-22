# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the AuthResolver credential-to-header resolution."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from flydek.catalog.enums import AuthType
from flydek.catalog.models import AuthConfig, Credential, ExternalSystem
from flydek.tools.auth_resolver import AuthResolver


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_system(
    auth_type: AuthType,
    credential_id: str = "cred-1",
    auth_headers: dict[str, str] | None = None,
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
def resolver(credential_store: MagicMock) -> AuthResolver:
    return AuthResolver(credential_store)


# ---------------------------------------------------------------------------
# Tests
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

        # Should use the first key from auth_headers dict.
        assert "Api-Token" in headers


class TestBasicAuth:
    async def test_returns_basic_header(self, resolver: AuthResolver, credential_store):
        # Basic auth expects base64-encoded "user:password".
        credential_store.get_credential.return_value = _make_credential(
            encrypted_value="dXNlcjpwYXNzd29yZA==",
        )
        system = _make_system(AuthType.BASIC)
        headers = await resolver.resolve_headers(system)

        assert headers == {"Authorization": "Basic dXNlcjpwYXNzd29yZA=="}


class TestOAuth2Auth:
    async def test_returns_bearer_header_as_placeholder(self, resolver: AuthResolver):
        """OAuth2 placeholder should return a Bearer header with the stored token."""
        system = _make_system(AuthType.OAUTH2)
        headers = await resolver.resolve_headers(system)

        assert headers == {"Authorization": "Bearer secret-token-123"}


class TestMissingCredential:
    async def test_raises_on_missing_credential(
        self, resolver: AuthResolver, credential_store
    ):
        credential_store.get_credential.return_value = None
        system = _make_system(AuthType.BEARER, credential_id="nonexistent")

        with pytest.raises(ValueError, match="not found"):
            await resolver.resolve_headers(system)


class TestUnsupportedAuthType:
    async def test_mutual_tls_returns_empty_headers(self, resolver: AuthResolver):
        system = _make_system(AuthType.MUTUAL_TLS)
        headers = await resolver.resolve_headers(system)

        assert headers == {}
