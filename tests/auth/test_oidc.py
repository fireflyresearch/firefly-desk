# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for OIDC discovery, JWT validation, token exchange, and PKCE."""

from __future__ import annotations

import base64
import hashlib
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from flydesk.auth.oidc import OIDCClient, OIDCDiscoveryDocument, generate_pkce_pair

# ---------------------------------------------------------------------------
# RSA key pair for JWT signing/verification in tests
# ---------------------------------------------------------------------------

_TEST_RSA_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_TEST_RSA_PUBLIC_KEY = _TEST_RSA_KEY.public_key()

# PEM-encoded public key numbers for JWKS construction
_PUBLIC_NUMBERS = _TEST_RSA_PUBLIC_KEY.public_numbers()


def _int_to_base64url(value: int) -> str:
    """Encode an integer as a base64url string (no padding)."""
    byte_length = (value.bit_length() + 7) // 8
    raw = value.to_bytes(byte_length, byteorder="big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


TEST_KID = "test-key-1"

TEST_JWKS: dict[str, Any] = {
    "keys": [
        {
            "kty": "RSA",
            "kid": TEST_KID,
            "use": "sig",
            "alg": "RS256",
            "n": _int_to_base64url(_PUBLIC_NUMBERS.n),
            "e": _int_to_base64url(_PUBLIC_NUMBERS.e),
        }
    ]
}

ISSUER = "https://idp.example.com"
CLIENT_ID = "test-client"

DISCOVERY_DATA: dict[str, str] = {
    "issuer": ISSUER,
    "authorization_endpoint": f"{ISSUER}/protocol/openid-connect/auth",
    "token_endpoint": f"{ISSUER}/protocol/openid-connect/token",
    "jwks_uri": f"{ISSUER}/protocol/openid-connect/certs",
    "userinfo_endpoint": f"{ISSUER}/protocol/openid-connect/userinfo",
    "end_session_endpoint": f"{ISSUER}/protocol/openid-connect/logout",
}


def _make_id_token(
    claims: dict[str, Any] | None = None,
    kid: str = TEST_KID,
) -> str:
    """Create a real RS256 JWT signed with the test RSA key."""
    payload: dict[str, Any] = {
        "iss": ISSUER,
        "aud": CLIENT_ID,
        "sub": "user-1",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    if claims:
        payload.update(claims)
    return jwt.encode(
        payload,
        _TEST_RSA_KEY,
        algorithm="RS256",
        headers={"kid": kid},
    )


def _httpx_response(data: dict | list, status_code: int = 200) -> MagicMock:
    """Create a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestOIDCDiscovery:
    async def test_discover_fetches_and_parses_document(self):
        """discover() GETs /.well-known/openid-configuration and returns a dataclass."""
        client = OIDCClient(issuer_url=ISSUER, client_id=CLIENT_ID)

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.get = AsyncMock(return_value=_httpx_response(DISCOVERY_DATA))

        with patch("flydesk.auth.oidc.httpx.AsyncClient", return_value=mock_http):
            doc = await client.discover()

        assert isinstance(doc, OIDCDiscoveryDocument)
        assert doc.issuer == ISSUER
        assert doc.authorization_endpoint == DISCOVERY_DATA["authorization_endpoint"]
        assert doc.token_endpoint == DISCOVERY_DATA["token_endpoint"]
        assert doc.jwks_uri == DISCOVERY_DATA["jwks_uri"]
        assert doc.userinfo_endpoint == DISCOVERY_DATA["userinfo_endpoint"]
        assert doc.end_session_endpoint == DISCOVERY_DATA["end_session_endpoint"]

    async def test_discover_caches_result(self):
        """Subsequent calls to discover() return the cached document."""
        client = OIDCClient(issuer_url=ISSUER, client_id=CLIENT_ID)

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.get = AsyncMock(return_value=_httpx_response(DISCOVERY_DATA))

        with patch("flydesk.auth.oidc.httpx.AsyncClient", return_value=mock_http):
            doc1 = await client.discover()
            doc2 = await client.discover()

        assert doc1 is doc2
        # httpx.AsyncClient was only constructed once (for the first call)
        assert mock_http.get.call_count == 1


class TestJWTValidation:
    async def test_validate_token_with_valid_jwt(self):
        """validate_token() successfully decodes a properly signed JWT."""
        client = OIDCClient(issuer_url=ISSUER, client_id=CLIENT_ID)
        token = _make_id_token({"email": "test@example.com"})

        # Pre-populate discovery and JWKS caches so no HTTP calls are needed
        doc = OIDCDiscoveryDocument(**DISCOVERY_DATA)
        client._discovery_cache = (time.monotonic(), doc)
        client._jwks_cache = (time.monotonic(), TEST_JWKS)

        claims = await client.validate_token(token)
        assert claims["sub"] == "user-1"
        assert claims["email"] == "test@example.com"
        assert claims["iss"] == ISSUER
        assert claims["aud"] == CLIENT_ID

    async def test_validate_token_rejects_expired_jwt(self):
        """validate_token() raises when the token has expired."""
        client = OIDCClient(issuer_url=ISSUER, client_id=CLIENT_ID)
        token = _make_id_token({"exp": int(time.time()) - 3600})

        doc = OIDCDiscoveryDocument(**DISCOVERY_DATA)
        client._discovery_cache = (time.monotonic(), doc)
        client._jwks_cache = (time.monotonic(), TEST_JWKS)

        with pytest.raises(jwt.exceptions.ExpiredSignatureError):
            await client.validate_token(token)

    async def test_validate_token_rejects_wrong_audience(self):
        """validate_token() rejects a token issued for a different audience."""
        client = OIDCClient(issuer_url=ISSUER, client_id="wrong-client-id")
        token = _make_id_token()

        doc = OIDCDiscoveryDocument(**DISCOVERY_DATA)
        client._discovery_cache = (time.monotonic(), doc)
        client._jwks_cache = (time.monotonic(), TEST_JWKS)

        with pytest.raises(jwt.exceptions.InvalidAudienceError):
            await client.validate_token(token)

    async def test_validate_token_refreshes_jwks_on_unknown_kid(self):
        """If the kid is not in the cached JWKS, the client refreshes."""
        client = OIDCClient(issuer_url=ISSUER, client_id=CLIENT_ID)
        token = _make_id_token()

        doc = OIDCDiscoveryDocument(**DISCOVERY_DATA)
        client._discovery_cache = (time.monotonic(), doc)

        # Generate a second RSA key with a different kid to populate initial JWKS.
        # The token's kid (TEST_KID) will NOT match, triggering a refresh.
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        other_pub = other_key.public_key().public_numbers()
        stale_jwks: dict[str, Any] = {
            "keys": [
                {
                    "kty": "RSA",
                    "kid": "old-key-that-does-not-match",
                    "use": "sig",
                    "alg": "RS256",
                    "n": _int_to_base64url(other_pub.n),
                    "e": _int_to_base64url(other_pub.e),
                }
            ]
        }
        client._jwks_cache = (time.monotonic(), stale_jwks)

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.get = AsyncMock(return_value=_httpx_response(TEST_JWKS))

        with patch("flydesk.auth.oidc.httpx.AsyncClient", return_value=mock_http):
            claims = await client.validate_token(token)

        assert claims["sub"] == "user-1"
        # JWKS was re-fetched
        assert mock_http.get.call_count == 1


class TestTokenExchange:
    async def test_exchange_code_posts_to_token_endpoint(self):
        """exchange_code() POSTs the authorization code to the token endpoint."""
        client = OIDCClient(
            issuer_url=ISSUER, client_id=CLIENT_ID, client_secret="s3cret"
        )
        doc = OIDCDiscoveryDocument(**DISCOVERY_DATA)
        client._discovery_cache = (time.monotonic(), doc)

        token_response = {
            "access_token": "at-123",
            "id_token": "id-456",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=_httpx_response(token_response))

        with patch("flydesk.auth.oidc.httpx.AsyncClient", return_value=mock_http):
            result = await client.exchange_code(
                code="auth-code-xyz",
                redirect_uri="http://localhost:3000/callback",
                code_verifier="verifier-abc",
            )

        assert result["access_token"] == "at-123"
        assert result["id_token"] == "id-456"

        # Verify the POST payload
        call_kwargs = mock_http.post.call_args
        posted_data = call_kwargs.kwargs.get("data") or call_kwargs[1].get("data")
        assert posted_data["grant_type"] == "authorization_code"
        assert posted_data["code"] == "auth-code-xyz"
        assert posted_data["client_id"] == CLIENT_ID
        assert posted_data["client_secret"] == "s3cret"
        assert posted_data["code_verifier"] == "verifier-abc"
        assert posted_data["redirect_uri"] == "http://localhost:3000/callback"


class TestBuildAuthUrl:
    def test_build_auth_url_with_discovery_doc(self):
        """build_auth_url() constructs a proper authorization URL."""
        client = OIDCClient(issuer_url=ISSUER, client_id=CLIENT_ID)
        doc = OIDCDiscoveryDocument(**DISCOVERY_DATA)

        url = client.build_auth_url(
            redirect_uri="http://localhost:3000/callback",
            state="random-state-token",
            scopes=["openid", "profile", "email"],
            code_challenge="challenge-abc",
            discovery_doc=doc,
        )

        assert url.startswith(doc.authorization_endpoint)
        assert "response_type=code" in url
        assert f"client_id={CLIENT_ID}" in url
        assert "state=random-state-token" in url
        assert "code_challenge=challenge-abc" in url
        assert "code_challenge_method=S256" in url
        assert "scope=openid+profile+email" in url


class TestPKCE:
    def test_generate_pkce_pair_verifier_length(self):
        """Code verifier is between 43 and 128 characters."""
        verifier, challenge = generate_pkce_pair()
        assert 43 <= len(verifier) <= 128

    def test_generate_pkce_pair_challenge_is_sha256_of_verifier(self):
        """The code challenge is a base64url-encoded SHA256 of the verifier."""
        verifier, challenge = generate_pkce_pair()

        expected_digest = hashlib.sha256(verifier.encode("ascii")).digest()
        expected_challenge = (
            base64.urlsafe_b64encode(expected_digest).rstrip(b"=").decode("ascii")
        )
        assert challenge == expected_challenge

    def test_generate_pkce_pair_is_unique(self):
        """Each call produces a distinct verifier/challenge pair."""
        pair1 = generate_pkce_pair()
        pair2 = generate_pkce_pair()
        assert pair1[0] != pair2[0]
        assert pair1[1] != pair2[1]
