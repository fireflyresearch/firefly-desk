# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for local JWT creation and verification."""

from __future__ import annotations

import secrets
from datetime import timedelta

import jwt as pyjwt
import pytest

from flydesk.auth.jwt_local import (
    LOCAL_ISSUER,
    create_local_jwt,
    decode_local_jwt,
)


class TestCreateLocalJwt:
    """Tests for ``create_local_jwt``."""

    def _make_token(self, **overrides) -> tuple[str, str]:
        """Helper that creates a token and returns (token, secret)."""
        secret = overrides.pop("secret_key", secrets.token_urlsafe(32))
        defaults = {
            "user_id": "usr_001",
            "email": "admin@flydesk.local",
            "display_name": "Admin User",
            "roles": ["admin"],
            "secret_key": secret,
        }
        defaults.update(overrides)
        return create_local_jwt(**defaults), secret

    def test_returns_valid_jwt_string(self):
        """create_local_jwt() returns a string with three dot-separated parts."""
        token, _ = self._make_token()
        assert isinstance(token, str)
        parts = token.split(".")
        assert len(parts) == 3, "JWT must have header.payload.signature"

    def test_contains_expected_claims(self):
        """Decoded token carries sub, email, name, roles, iss, iat, exp."""
        token, secret = self._make_token()
        claims = pyjwt.decode(token, secret, algorithms=["HS256"], issuer=LOCAL_ISSUER)
        assert claims["sub"] == "usr_001"
        assert claims["email"] == "admin@flydesk.local"
        assert claims["name"] == "Admin User"
        assert claims["roles"] == ["admin"]
        assert claims["iss"] == LOCAL_ISSUER
        assert "iat" in claims
        assert "exp" in claims

    def test_custom_expiry(self):
        """The token respects a custom expires_delta."""
        token, secret = self._make_token(expires_delta=timedelta(minutes=5))
        claims = pyjwt.decode(token, secret, algorithms=["HS256"], issuer=LOCAL_ISSUER)
        lifetime = claims["exp"] - claims["iat"]
        assert lifetime == 300  # 5 minutes in seconds

    def test_multiple_roles(self):
        """Multiple roles are preserved in the token."""
        token, secret = self._make_token(roles=["admin", "agent", "supervisor"])
        claims = pyjwt.decode(token, secret, algorithms=["HS256"], issuer=LOCAL_ISSUER)
        assert claims["roles"] == ["admin", "agent", "supervisor"]


class TestDecodeLocalJwt:
    """Tests for ``decode_local_jwt``."""

    def test_roundtrip(self):
        """A token created with create_local_jwt is decoded successfully."""
        secret = secrets.token_urlsafe(32)
        token = create_local_jwt(
            user_id="usr_002",
            email="agent@flydesk.local",
            display_name="Agent User",
            roles=["agent"],
            secret_key=secret,
        )
        claims = decode_local_jwt(token, secret)
        assert claims["sub"] == "usr_002"
        assert claims["email"] == "agent@flydesk.local"
        assert claims["name"] == "Agent User"
        assert claims["roles"] == ["agent"]

    def test_wrong_secret_raises(self):
        """Decoding with the wrong secret raises InvalidSignatureError."""
        token = create_local_jwt(
            user_id="usr_003",
            email="x@y.com",
            display_name="X",
            roles=[],
            secret_key="correct-secret",
        )
        with pytest.raises(pyjwt.InvalidSignatureError):
            decode_local_jwt(token, "wrong-secret")

    def test_expired_token_raises(self):
        """An expired token raises ExpiredSignatureError."""
        secret = secrets.token_urlsafe(32)
        token = create_local_jwt(
            user_id="usr_004",
            email="exp@flydesk.local",
            display_name="Expired",
            roles=[],
            secret_key=secret,
            expires_delta=timedelta(seconds=-1),
        )
        with pytest.raises(pyjwt.ExpiredSignatureError):
            decode_local_jwt(token, secret)

    def test_tampered_issuer_raises(self):
        """A token with a non-matching issuer raises InvalidIssuerError."""
        secret = secrets.token_urlsafe(32)
        # Manually craft a token with wrong issuer
        payload = {
            "sub": "usr_005",
            "email": "bad@iss.com",
            "name": "Bad Issuer",
            "roles": [],
            "iss": "some-other-issuer",
            "iat": 0,
            "exp": 9999999999,
        }
        token = pyjwt.encode(payload, secret, algorithm="HS256")
        with pytest.raises(pyjwt.InvalidIssuerError):
            decode_local_jwt(token, secret)
