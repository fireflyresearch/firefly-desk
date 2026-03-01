# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for email domain filtering in the OIDC auth callback."""

from __future__ import annotations

import base64
import json
import os
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.api.auth import (
    _check_email_domain,
    _extract_email_from_id_token,
    _parse_domains,
    _store_state,
)
from flydesk.auth.oidc import OIDCClient, OIDCDiscoveryDocument
from flydesk.auth.repository import OIDCProviderRepository
from flydesk.models.base import Base

ISSUER = "https://idp.example.com"
DISCOVERY_DOC = OIDCDiscoveryDocument(
    issuer=ISSUER,
    authorization_endpoint=f"{ISSUER}/protocol/openid-connect/auth",
    token_endpoint=f"{ISSUER}/protocol/openid-connect/token",
    jwks_uri=f"{ISSUER}/protocol/openid-connect/certs",
    userinfo_endpoint=f"{ISSUER}/protocol/openid-connect/userinfo",
    end_session_endpoint=f"{ISSUER}/protocol/openid-connect/logout",
)


def _make_id_token(email: str | None = None) -> str:
    """Build a fake JWT id_token with an optional email claim."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256"}).encode()).rstrip(b"=")
    payload_data: dict[str, Any] = {"sub": "user-1", "iss": ISSUER}
    if email is not None:
        payload_data["email"] = email
    payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).rstrip(b"=")
    sig = base64.urlsafe_b64encode(b"fake-signature").rstrip(b"=")
    return f"{header.decode()}.{payload.decode()}.{sig.decode()}"


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestParseDomains:
    """Unit tests for _parse_domains()."""

    def test_none_returns_empty_set(self):
        assert _parse_domains(None) == set()

    def test_empty_string_returns_empty_set(self):
        assert _parse_domains("") == set()

    def test_empty_list_returns_empty_set(self):
        assert _parse_domains([]) == set()

    def test_json_string_list(self):
        raw = json.dumps(["Company.com", "partner.ORG"])
        result = _parse_domains(raw)
        assert result == {"company.com", "partner.org"}

    def test_python_list(self):
        result = _parse_domains(["Alpha.Com", "BETA.org"])
        assert result == {"alpha.com", "beta.org"}

    def test_strips_whitespace(self):
        result = _parse_domains(["  example.com  ", " test.org "])
        assert result == {"example.com", "test.org"}

    def test_filters_empty_strings(self):
        result = _parse_domains(["valid.com", "", "  ", "ok.org"])
        assert result == {"valid.com", "ok.org"}

    def test_invalid_json_string(self):
        assert _parse_domains("not valid json") == set()

    def test_non_list_non_string_returns_empty(self):
        assert _parse_domains(42) == set()
        assert _parse_domains({"a": 1}) == set()


class TestExtractEmailFromIdToken:
    """Unit tests for _extract_email_from_id_token()."""

    def test_extracts_email(self):
        token = _make_id_token("user@company.com")
        assert _extract_email_from_id_token(token) == "user@company.com"

    def test_no_email_claim(self):
        token = _make_id_token(None)
        assert _extract_email_from_id_token(token) is None

    def test_none_token(self):
        assert _extract_email_from_id_token(None) is None

    def test_empty_token(self):
        assert _extract_email_from_id_token("") is None

    def test_malformed_token(self):
        assert _extract_email_from_id_token("not-a-jwt") is None

    def test_single_segment_token(self):
        assert _extract_email_from_id_token("onlyone") is None


class TestCheckEmailDomain:
    """Unit tests for _check_email_domain()."""

    def test_allowed_domain_passes(self):
        # Should not raise
        _check_email_domain("user@company.com", {"company.com"})

    def test_blocked_domain_raises_403(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _check_email_domain("user@evil.com", {"company.com"})
        assert exc_info.value.status_code == 403
        assert "evil.com" in exc_info.value.detail

    def test_empty_allowed_domains_allows_all(self):
        # Should not raise
        _check_email_domain("user@anything.com", set())

    def test_none_email_allows_through(self):
        # Should not raise
        _check_email_domain(None, {"company.com"})

    def test_empty_email_allows_through(self):
        _check_email_domain("", {"company.com"})

    def test_no_at_sign_allows_through(self):
        _check_email_domain("no-at-sign", {"company.com"})

    def test_case_insensitive_domain(self):
        # Domain extraction lowercases
        _check_email_domain("user@COMPANY.COM", {"company.com"})

    def test_multiple_allowed_domains(self):
        allowed = {"company.com", "partner.org", "subsidiary.io"}
        _check_email_domain("user@partner.org", allowed)
        _check_email_domain("admin@subsidiary.io", allowed)


# ---------------------------------------------------------------------------
# Integration tests — full HTTP callback flow
# ---------------------------------------------------------------------------


@pytest.fixture
async def _domain_fixtures():
    """Set up in-memory DB with providers for domain filtering tests."""
    encryption_key = Fernet.generate_key().decode()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    repo = OIDCProviderRepository(session_factory, encryption_key)

    # Provider with domain restrictions
    restricted = await repo.create_provider(
        provider_type="keycloak",
        display_name="Restricted Provider",
        issuer_url=ISSUER,
        client_id="restricted-client",
        client_secret="secret",
        scopes=["openid", "profile", "email"],
        allowed_email_domains=["company.com", "partner.org"],
        is_active=True,
    )

    # Provider without domain restrictions (all allowed)
    unrestricted = await repo.create_provider(
        provider_type="keycloak",
        display_name="Open Provider",
        issuer_url=ISSUER,
        client_id="open-client",
        client_secret="secret",
        scopes=["openid", "profile", "email"],
        is_active=True,
    )

    # Provider with empty list (also means all allowed)
    empty_domains = await repo.create_provider(
        provider_type="keycloak",
        display_name="Empty Domains Provider",
        issuer_url=ISSUER,
        client_id="empty-client",
        client_secret="secret",
        scopes=["openid", "profile", "email"],
        allowed_email_domains=[],
        is_active=True,
    )

    yield {
        "repo": repo,
        "encryption_key": encryption_key,
        "restricted_id": restricted.id,
        "unrestricted_id": unrestricted.id,
        "empty_domains_id": empty_domains.id,
    }
    await engine.dispose()


@pytest.fixture
async def client(_domain_fixtures):
    """AsyncClient with auth dependency overrides for domain filtering tests."""
    repo = _domain_fixtures["repo"]
    encryption_key = _domain_fixtures["encryption_key"]

    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_DEV_MODE": "true",
        "FLYDESK_OIDC_ISSUER_URL": ISSUER,
        "FLYDESK_OIDC_CLIENT_ID": "test-client",
        "FLYDESK_OIDC_CLIENT_SECRET": "secret",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": encryption_key,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.auth import get_oidc_repo
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_oidc_repo] = lambda: repo

        from flydesk.api.deps import get_audit_logger
        app.dependency_overrides[get_audit_logger] = lambda: AsyncMock()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


async def _do_callback(
    client: AsyncClient,
    fixtures: dict,
    provider_id: str,
    userinfo_email: str | None,
    id_token_email: str | None = None,
) -> Any:
    """Helper to perform a full callback flow with mocked OIDC exchange.

    Returns the httpx Response object.
    """
    # Inject a pending state for the provider
    state = "test-state-" + provider_id
    _store_state(state, {
        "provider_id": provider_id,
        "redirect_uri": "http://localhost:3000/callback",
    })

    # Build the tokens the mock exchange will return
    id_token = _make_id_token(id_token_email) if id_token_email is not None else None
    mock_tokens = {
        "access_token": "mock-access-token",
        "id_token": id_token,
        "expires_in": 3600,
    }

    # Build the userinfo the mock will return
    mock_userinfo: dict[str, Any] = {"sub": "user-1"}
    if userinfo_email is not None:
        mock_userinfo["email"] = userinfo_email

    with (
        patch.object(
            OIDCClient,
            "exchange_code",
            new_callable=AsyncMock,
            return_value=mock_tokens,
        ),
        patch.object(
            OIDCClient,
            "get_userinfo",
            new_callable=AsyncMock,
            return_value=mock_userinfo,
        ),
    ):
        return await client.post(
            "/api/auth/callback",
            json={"code": "auth-code-123", "state": state},
        )


class TestDomainFilteringIntegration:
    """Integration tests for email domain filtering in auth_callback."""

    async def test_allowed_domain_passes(self, client: AsyncClient, _domain_fixtures):
        """User with an allowed email domain gets a 200 with tokens."""
        resp = await _do_callback(
            client,
            _domain_fixtures,
            _domain_fixtures["restricted_id"],
            userinfo_email="alice@company.com",
            id_token_email="alice@company.com",
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"] == "mock-access-token"
        assert body["user_info"]["email"] == "alice@company.com"

    async def test_second_allowed_domain_passes(self, client: AsyncClient, _domain_fixtures):
        """User with another allowed domain (partner.org) also passes."""
        resp = await _do_callback(
            client,
            _domain_fixtures,
            _domain_fixtures["restricted_id"],
            userinfo_email="bob@partner.org",
            id_token_email="bob@partner.org",
        )
        assert resp.status_code == 200

    async def test_blocked_domain_returns_403(self, client: AsyncClient, _domain_fixtures):
        """User with a non-allowed domain gets a 403."""
        resp = await _do_callback(
            client,
            _domain_fixtures,
            _domain_fixtures["restricted_id"],
            userinfo_email="hacker@evil.com",
            id_token_email="hacker@evil.com",
        )
        assert resp.status_code == 403
        body = resp.json()
        assert "evil.com" in body["detail"]
        assert "not allowed" in body["detail"]

    async def test_no_allowed_domains_allows_all(self, client: AsyncClient, _domain_fixtures):
        """Provider with no allowed_email_domains allows any email."""
        resp = await _do_callback(
            client,
            _domain_fixtures,
            _domain_fixtures["unrestricted_id"],
            userinfo_email="anyone@anywhere.com",
        )
        assert resp.status_code == 200

    async def test_empty_allowed_domains_allows_all(self, client: AsyncClient, _domain_fixtures):
        """Provider with empty allowed_email_domains list allows any email."""
        resp = await _do_callback(
            client,
            _domain_fixtures,
            _domain_fixtures["empty_domains_id"],
            userinfo_email="anyone@anywhere.com",
        )
        assert resp.status_code == 200

    async def test_no_email_in_userinfo_allowed(self, client: AsyncClient, _domain_fixtures):
        """When userinfo has no email, the user is still allowed through."""
        resp = await _do_callback(
            client,
            _domain_fixtures,
            _domain_fixtures["restricted_id"],
            userinfo_email=None,
            id_token_email=None,
        )
        assert resp.status_code == 200

    async def test_id_token_fast_path_blocks_before_userinfo(
        self, client: AsyncClient, _domain_fixtures
    ):
        """If id_token email is blocked, 403 happens even before userinfo check."""
        # id_token has blocked email; userinfo would have allowed email
        # but the id_token check fires first and blocks.
        state = "test-state-fast-path"
        _store_state(state, {
            "provider_id": _domain_fixtures["restricted_id"],
            "redirect_uri": "http://localhost:3000/callback",
        })

        id_token = _make_id_token("hacker@blocked.com")
        mock_tokens = {
            "access_token": "mock-access-token",
            "id_token": id_token,
            "expires_in": 3600,
        }

        userinfo_mock = AsyncMock(return_value={"sub": "user-1", "email": "good@company.com"})

        with (
            patch.object(
                OIDCClient,
                "exchange_code",
                new_callable=AsyncMock,
                return_value=mock_tokens,
            ),
            patch.object(
                OIDCClient,
                "get_userinfo",
                userinfo_mock,
            ),
        ):
            resp = await client.post(
                "/api/auth/callback",
                json={"code": "auth-code-123", "state": state},
            )

        assert resp.status_code == 403
        assert "blocked.com" in resp.json()["detail"]

    async def test_blocked_domain_does_not_set_cookie(
        self, client: AsyncClient, _domain_fixtures
    ):
        """A blocked domain should not result in a session cookie being set."""
        resp = await _do_callback(
            client,
            _domain_fixtures,
            _domain_fixtures["restricted_id"],
            userinfo_email="hacker@evil.com",
            id_token_email="hacker@evil.com",
        )
        assert resp.status_code == 403
        # Should not have set a flydesk_token cookie
        set_cookie = resp.headers.get("set-cookie", "")
        assert "flydesk_token" not in set_cookie

    async def test_case_insensitive_matching(self, client: AsyncClient, _domain_fixtures):
        """Domain matching is case-insensitive."""
        resp = await _do_callback(
            client,
            _domain_fixtures,
            _domain_fixtures["restricted_id"],
            userinfo_email="alice@COMPANY.COM",
            id_token_email="alice@Company.Com",
        )
        assert resp.status_code == 200
