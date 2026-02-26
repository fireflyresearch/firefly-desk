# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Resolve authentication headers for external system calls.

Supports all auth types defined in :class:`~flydesk.catalog.enums.AuthType`:
BEARER, API_KEY, BASIC, OAUTH2 (client credentials grant), and MUTUAL_TLS.
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

import httpx

from flydesk.catalog.enums import AuthType

if TYPE_CHECKING:
    from flydesk.catalog.ports import CredentialStore
    from flydesk.auth.models import UserSession
    from flydesk.auth.sso_mapping import SSOAttributeMapping
    from flydesk.catalog.models import ExternalSystem
    from flydesk.security.kms import KMSProvider

logger = logging.getLogger(__name__)


class _TokenCache:
    """In-memory cache for OAuth2 access tokens.

    Stores tokens keyed by (system_id, credential_id) with expiry tracking.
    Tokens are refreshed when within 60 seconds of expiration.
    """

    def __init__(self) -> None:
        self._cache: dict[str, tuple[str, float]] = {}  # key -> (token, expires_at)
        self._buffer_seconds = 60

    def get(self, key: str) -> str | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        token, expires_at = entry
        if time.monotonic() >= expires_at - self._buffer_seconds:
            del self._cache[key]
            return None
        return token

    def put(self, key: str, token: str, expires_in: int) -> None:
        self._cache[key] = (token, time.monotonic() + expires_in)


class AuthResolver:
    """Resolves authentication headers for a given :class:`ExternalSystem`.

    Supported auth types:

    - **BEARER** -- ``Authorization: Bearer <token>``
    - **API_KEY** -- Custom header from ``auth_config.auth_headers`` with the
      credential value.
    - **BASIC** -- ``Authorization: Basic <base64-encoded-credentials>``
    - **OAUTH2** -- Client credentials grant flow with token caching and
      automatic refresh.  Uses ``auth_config.token_url`` and
      ``auth_config.scopes``.
    - **MUTUAL_TLS** -- Returns custom auth headers from ``auth_config.auth_headers``
      (certificate handling is at the HTTP client level).
    """

    def __init__(
        self,
        credential_store: CredentialStore,
        http_client: httpx.AsyncClient | None = None,
        kms: KMSProvider | None = None,
    ) -> None:
        self._credential_store = credential_store
        self._http_client = http_client
        self._kms = kms
        self._token_cache = _TokenCache()

    def _decrypt(self, ciphertext: str) -> str:
        """Decrypt a credential value using the configured KMS.

        Falls back to returning the value as-is when no KMS is configured
        (backward-compatible with unencrypted credentials).
        """
        if self._kms is None:
            return ciphertext
        try:
            return self._kms.decrypt(ciphertext)
        except (ValueError, Exception):
            # Likely an unencrypted legacy value -- return as-is.
            logger.debug("KMS decryption failed; using value as-is.")
            return ciphertext

    async def resolve_headers(
        self,
        system: ExternalSystem,
        user_session: UserSession | None = None,
        sso_mappings: list[SSOAttributeMapping] | None = None,
    ) -> dict[str, str]:
        """Return a dict of HTTP headers that authenticate against *system*.

        When *user_session* and *sso_mappings* are provided, SSO claim values
        are resolved and merged into the returned headers so that downstream
        APIs can identify the originating user.
        """
        auth_config = system.auth_config

        # No authentication required.
        if auth_config is None or auth_config.auth_type == AuthType.NONE:
            headers: dict[str, str] = {}
            if user_session and sso_mappings:
                from flydesk.auth.sso_mapping import SSOAttributeMappingResolver

                resolver = SSOAttributeMappingResolver()
                sso_headers = resolver.resolve_headers(
                    sso_mappings, user_session.raw_claims, system.id,
                )
                headers.update(sso_headers)
            return headers

        auth_type = auth_config.auth_type

        credential = await self._credential_store.get_credential(
            auth_config.credential_id,
        )
        if credential is None:
            msg = (
                f"Credential {auth_config.credential_id!r} not found "
                f"for system {system.id!r}"
            )
            raise ValueError(msg)

        token = self._decrypt(credential.encrypted_value)

        if auth_type == AuthType.BEARER:
            headers = {"Authorization": f"Bearer {token}"}
        elif auth_type == AuthType.API_KEY:
            header_name = "X-Api-Key"
            if auth_config.auth_headers:
                header_name = next(iter(auth_config.auth_headers))
            headers = {header_name: token}
        elif auth_type == AuthType.BASIC:
            headers = {"Authorization": f"Basic {token}"}
        elif auth_type == AuthType.OAUTH2:
            headers = await self._resolve_oauth2(system, credential)
        elif auth_type == AuthType.MUTUAL_TLS:
            # mTLS certificate handling is done at the HTTP client level.
            # Return any additional auth headers the system requires.
            headers = {}
            if auth_config.auth_headers:
                headers.update(auth_config.auth_headers)
        else:
            logger.warning(
                "Unknown auth type %s for system %s; returning empty headers",
                auth_type,
                system.id,
            )
            headers = {}

        # Apply SSO claim mappings
        if user_session and sso_mappings:
            from flydesk.auth.sso_mapping import SSOAttributeMappingResolver

            resolver = SSOAttributeMappingResolver()
            sso_headers = resolver.resolve_headers(
                sso_mappings, user_session.raw_claims, system.id,
            )
            headers.update(sso_headers)

        return headers

    async def _resolve_oauth2(
        self, system: ExternalSystem, credential: object
    ) -> dict[str, str]:
        """Perform OAuth2 client credentials grant with token caching.

        The credential's ``encrypted_value`` is expected to be a JSON object:
        ``{"client_id": "...", "client_secret": "..."}``.

        If parsing fails, the encrypted_value is treated as a pre-obtained
        access token (backward-compatible fallback).
        """
        auth_config = system.auth_config
        cache_key = f"{system.id}:{auth_config.credential_id}"

        # Check cache first
        cached = self._token_cache.get(cache_key)
        if cached:
            return {"Authorization": f"Bearer {cached}"}

        token_value = self._decrypt(credential.encrypted_value)  # type: ignore[attr-defined]

        # Try to parse as client credentials JSON
        client_id: str | None = None
        client_secret: str | None = None
        try:
            creds = json.loads(token_value)
            if isinstance(creds, dict):
                client_id = creds.get("client_id")
                client_secret = creds.get("client_secret")
        except (json.JSONDecodeError, TypeError):
            pass

        # If we have client_id + client_secret + token_url, do real exchange
        if client_id and client_secret and auth_config.token_url:
            access_token = await self._exchange_token(
                token_url=auth_config.token_url,
                client_id=client_id,
                client_secret=client_secret,
                scopes=auth_config.scopes,
                cache_key=cache_key,
            )
            if access_token:
                return {"Authorization": f"Bearer {access_token}"}

            # Exchange failed — fall through to use raw token
            logger.warning(
                "OAuth2 token exchange failed for system %s; "
                "using stored credential as bearer token",
                system.id,
            )

        # Fallback: use the stored value as a pre-obtained access token
        return {"Authorization": f"Bearer {token_value}"}

    async def _exchange_token(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        scopes: list[str] | None,
        cache_key: str,
    ) -> str | None:
        """Execute the OAuth2 client credentials grant."""
        if not self._http_client:
            logger.warning("No HTTP client configured for OAuth2 token exchange")
            return None

        payload: dict[str, str] = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
        if scopes:
            payload["scope"] = " ".join(scopes)

        try:
            response = await self._http_client.post(
                token_url,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            access_token = data.get("access_token")
            if not access_token:
                logger.error("OAuth2 response missing access_token: %s", data)
                return None

            # Cache with expiry (default 1 hour if not specified)
            expires_in = int(data.get("expires_in", 3600))
            self._token_cache.put(cache_key, access_token, expires_in)

            logger.debug(
                "OAuth2 token obtained for %s (expires in %ds)",
                cache_key,
                expires_in,
            )
            return access_token

        except httpx.HTTPStatusError as exc:
            logger.error(
                "OAuth2 token exchange HTTP %s: %s",
                exc.response.status_code,
                exc.response.text[:200],
            )
            return None
        except Exception:
            logger.error("OAuth2 token exchange failed", exc_info=True)
            return None
