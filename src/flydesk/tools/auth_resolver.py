# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Resolve authentication headers for external system calls."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from flydesk.catalog.enums import AuthType

if TYPE_CHECKING:
    from flydesk.api.credentials import CredentialStore
    from flydesk.catalog.models import ExternalSystem

logger = logging.getLogger(__name__)


class AuthResolver:
    """Resolves authentication headers for a given :class:`ExternalSystem`.

    Supported auth types:

    - **BEARER** -- ``Authorization: Bearer <token>``
    - **API_KEY** -- Custom header from ``auth_config.auth_headers`` with the
      credential value.
    - **BASIC** -- ``Authorization: Basic <base64-encoded-credentials>``
    - **OAUTH2** -- Placeholder that returns a Bearer header (real OAuth2 code
      exchange flow will be implemented in a future phase).
    """

    def __init__(self, credential_store: CredentialStore) -> None:
        self._credential_store = credential_store

    async def resolve_headers(self, system: ExternalSystem) -> dict[str, str]:
        """Return a dict of HTTP headers that authenticate against *system*."""
        auth_config = system.auth_config
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

        # The stored value is the encrypted_value field; in a real deployment
        # this would be decrypted transparently by the credential store.
        token = credential.encrypted_value

        if auth_type == AuthType.BEARER:
            return {"Authorization": f"Bearer {token}"}

        if auth_type == AuthType.API_KEY:
            # The header name is stored in auth_config.auth_headers,
            # e.g. {"X-Api-Key": ""}.  We use the first key found.
            header_name = "X-Api-Key"
            if auth_config.auth_headers:
                header_name = next(iter(auth_config.auth_headers))
            return {header_name: token}

        if auth_type == AuthType.BASIC:
            return {"Authorization": f"Basic {token}"}

        if auth_type == AuthType.OAUTH2:
            # Placeholder: treat the stored credential as an access token.
            # A real implementation would perform token exchange / refresh.
            logger.debug(
                "OAuth2 auth for system %s -- using stored token as bearer",
                system.id,
            )
            return {"Authorization": f"Bearer {token}"}

        # Unsupported types (e.g. MUTUAL_TLS) -- return empty headers for now.
        logger.warning(
            "Unsupported auth type %s for system %s; returning empty headers",
            auth_type,
            system.id,
        )
        return {}
