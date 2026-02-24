# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Local JWT creation and verification for Firefly Desk.

When running in local-auth mode (no external OIDC provider), Firefly Desk
issues its own JWTs signed with HS256.  These tokens carry the same claims
that the OIDC middleware expects (``sub``, ``email``, ``name``, ``roles``),
so the rest of the application can handle them uniformly.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt

LOCAL_ISSUER = "flydesk-local"
_ALGORITHM = "HS256"


def create_local_jwt(
    user_id: str,
    email: str,
    display_name: str,
    roles: list[str],
    secret_key: str,
    expires_delta: timedelta = timedelta(hours=24),
) -> str:
    """Create a signed JWT for local authentication.

    Parameters
    ----------
    user_id:
        Unique user identifier (stored in the ``sub`` claim).
    email:
        User email address.
    display_name:
        Human-readable display name.
    roles:
        List of role strings (e.g. ``["admin", "agent"]``).
    secret_key:
        HMAC secret used to sign the token.
    expires_delta:
        Token lifetime.  Defaults to 24 hours.

    Returns
    -------
    str
        An encoded JWT string.
    """
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "email": email,
        "name": display_name,
        "roles": roles,
        "iss": LOCAL_ISSUER,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, secret_key, algorithm=_ALGORITHM)


def decode_local_jwt(token: str, secret_key: str) -> dict:
    """Decode and verify a locally-issued JWT.

    Parameters
    ----------
    token:
        The encoded JWT string.
    secret_key:
        HMAC secret that was used to sign the token.

    Returns
    -------
    dict
        The decoded claims payload.

    Raises
    ------
    jwt.ExpiredSignatureError
        If the token has expired.
    jwt.InvalidIssuerError
        If the ``iss`` claim does not match ``flydesk-local``.
    jwt.InvalidTokenError
        For any other validation failure.
    """
    return jwt.decode(
        token,
        secret_key,
        algorithms=[_ALGORITHM],
        issuer=LOCAL_ISSUER,
    )
