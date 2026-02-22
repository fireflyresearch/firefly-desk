# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""OIDC discovery, JWT validation, and authorization code exchange."""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

logger = logging.getLogger(__name__)

# Supported JWT signing algorithms
_ALGORITHMS = ["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"]

# Cache TTL for the discovery document (1 hour)
_DISCOVERY_TTL_SECONDS = 3600


@dataclass(frozen=True)
class OIDCDiscoveryDocument:
    """Parsed OpenID Connect discovery document."""

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    userinfo_endpoint: str
    end_session_endpoint: str = ""


@dataclass
class OIDCClient:
    """Client for OpenID Connect operations.

    Handles discovery, JWT validation, authorization code exchange, and
    userinfo retrieval for a single OIDC issuer.
    """

    issuer_url: str
    client_id: str
    client_secret: str = ""

    # Internal cache: (timestamp, document)
    _discovery_cache: tuple[float, OIDCDiscoveryDocument | None] = field(
        default=(0.0, None), init=False, repr=False
    )
    _jwks_cache: tuple[float, dict[str, Any] | None] = field(
        default=(0.0, None), init=False, repr=False
    )

    # -- Discovery --

    async def discover(self) -> OIDCDiscoveryDocument:
        """Fetch the OIDC discovery document, caching for 1 hour."""
        now = time.monotonic()
        cached_ts, cached_doc = self._discovery_cache
        if cached_doc is not None and (now - cached_ts) < _DISCOVERY_TTL_SECONDS:
            return cached_doc

        url = self.issuer_url.rstrip("/") + "/.well-known/openid-configuration"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()

        doc = OIDCDiscoveryDocument(
            issuer=data["issuer"],
            authorization_endpoint=data["authorization_endpoint"],
            token_endpoint=data["token_endpoint"],
            jwks_uri=data["jwks_uri"],
            userinfo_endpoint=data.get("userinfo_endpoint", ""),
            end_session_endpoint=data.get("end_session_endpoint", ""),
        )
        self._discovery_cache = (now, doc)
        return doc

    # -- JWKS --

    async def fetch_jwks(self) -> dict[str, Any]:
        """Fetch the JSON Web Key Set from the JWKS URI."""
        now = time.monotonic()
        cached_ts, cached_jwks = self._jwks_cache
        if cached_jwks is not None and (now - cached_ts) < _DISCOVERY_TTL_SECONDS:
            return cached_jwks

        doc = await self.discover()
        async with httpx.AsyncClient() as client:
            resp = await client.get(doc.jwks_uri, timeout=10.0)
            resp.raise_for_status()
            jwks = resp.json()

        self._jwks_cache = (now, jwks)
        return jwks

    # -- Token validation --

    async def validate_token(self, token: str) -> dict[str, Any]:
        """Validate a JWT access/ID token against the OIDC issuer.

        Verifies the signature using the issuer's JWKS and checks standard
        claims: ``exp``, ``iss``, and ``aud``.
        """
        jwks = await self.fetch_jwks()
        signing_keys = jwt.PyJWKSet.from_dict(jwks)

        try:
            header = jwt.get_unverified_header(token)
        except jwt.exceptions.DecodeError as exc:
            msg = "Invalid JWT header"
            raise jwt.exceptions.InvalidTokenError(msg) from exc

        kid = header.get("kid")
        key = None
        for jwk in signing_keys.keys:
            if jwk.key_id == kid:
                key = jwk
                break

        if key is None:
            # Refresh JWKS in case keys were rotated
            self._jwks_cache = (0.0, None)
            jwks = await self.fetch_jwks()
            signing_keys = jwt.PyJWKSet.from_dict(jwks)
            for jwk in signing_keys.keys:
                if jwk.key_id == kid:
                    key = jwk
                    break
            if key is None:
                msg = f"No matching key found for kid={kid}"
                raise jwt.exceptions.InvalidTokenError(msg)

        claims: dict[str, Any] = jwt.decode(
            token,
            key=key.key,
            algorithms=_ALGORITHMS,
            issuer=self.issuer_url.rstrip("/"),
            audience=self.client_id,
            options={"verify_exp": True, "verify_iss": True, "verify_aud": True},
        )
        return claims

    # -- Authorization code exchange --

    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        code_verifier: str | None = None,
    ) -> dict[str, Any]:
        """Exchange an authorization code for tokens at the token endpoint."""
        doc = await self.discover()
        payload: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.client_id,
        }
        if self.client_secret:
            payload["client_secret"] = self.client_secret
        if code_verifier:
            payload["code_verifier"] = code_verifier

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                doc.token_endpoint,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()

    # -- Userinfo --

    async def get_userinfo(self, access_token: str) -> dict[str, Any]:
        """Fetch user profile data from the userinfo endpoint."""
        doc = await self.discover()
        if not doc.userinfo_endpoint:
            return {}

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                doc.userinfo_endpoint,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )
            resp.raise_for_status()
            return resp.json()

    # -- Build authorization URL --

    def build_auth_url(
        self,
        redirect_uri: str,
        state: str,
        scopes: list[str],
        code_challenge: str | None = None,
        discovery_doc: OIDCDiscoveryDocument | None = None,
    ) -> str:
        """Construct the authorization URL for the OIDC provider.

        ``discovery_doc`` must be passed in if it has already been fetched
        (this method is synchronous and cannot perform I/O).  If ``None``,
        a fallback URL is constructed from the issuer URL.
        """
        if discovery_doc is not None:
            auth_endpoint = discovery_doc.authorization_endpoint
        else:
            # Fallback: caller should pre-fetch discovery
            auth_endpoint = self.issuer_url.rstrip("/") + "/protocol/openid-connect/auth"

        params: dict[str, str] = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": " ".join(scopes),
        }
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"

        return f"{auth_endpoint}?{urlencode(params)}"


# -- PKCE helpers --


def generate_pkce_pair() -> tuple[str, str]:
    """Generate a PKCE code verifier and its S256 code challenge.

    Returns:
        A tuple of ``(code_verifier, code_challenge)``.
    """
    code_verifier = secrets.token_urlsafe(64)[:128]  # 43-128 URL-safe chars
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge
