# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""SSO attribute mapping -- resolve SSO claims into HTTP headers/params for API calls.

When the agent calls backoffice APIs on behalf of a user, SSO claims such as
``employee_id`` can be forwarded as HTTP headers (e.g. ``X-Employee-ID``) so
the downstream system recognises the originating user.
"""

from __future__ import annotations

import base64
import logging
from typing import Any, Literal

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class SSOAttributeMapping(BaseModel):
    """A single mapping from an SSO claim to an outbound HTTP header or query param."""

    id: str
    claim_path: str
    """Dot-notation path into the raw claims dict, e.g. ``"employee_id"``
    or ``"custom_claims.hr_id"``."""

    target_header: str
    """The name of the HTTP header (or query parameter) to set."""

    target_type: Literal["header", "query_param"] = "header"

    system_filter: str | None = None
    """When set, this mapping only applies to calls targeting the given system ID."""

    transform: str | None = None
    """Optional transform to apply to the extracted claim value.

    Supported transforms:

    * ``"uppercase"`` -- ``value.upper()``
    * ``"lowercase"`` -- ``value.lower()``
    * ``"prefix:EMP-"`` -- prepend a literal prefix
    * ``"base64"`` -- Base64-encode the value
    * ``None`` -- pass-through (no transform)
    """


def _extract_claim(raw_claims: dict[str, Any], claim_path: str) -> str | None:
    """Walk *raw_claims* using dot-notation *claim_path* and return the leaf value.

    Returns ``None`` when any segment along the path is missing.
    """
    parts = claim_path.split(".")
    current: Any = raw_claims
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if current is None:
            return None
    return str(current)


def _apply_transform(value: str, transform: str | None) -> str:
    """Apply the configured transform to *value*."""
    if transform is None:
        return value
    if transform == "uppercase":
        return value.upper()
    if transform == "lowercase":
        return value.lower()
    if transform.startswith("prefix:"):
        prefix = transform[len("prefix:"):]
        return prefix + value
    if transform == "base64":
        return base64.b64encode(value.encode()).decode()
    logger.warning("Unknown SSO mapping transform %r; returning value as-is", transform)
    return value


class SSOAttributeMappingResolver:
    """Resolves SSO claim values into HTTP headers/params for API calls."""

    def resolve_headers(
        self,
        mappings: list[SSOAttributeMapping],
        raw_claims: dict[str, Any],
        system_id: str | None = None,
    ) -> dict[str, str]:
        """Apply *mappings* to extract claim values and return a headers dict.

        For each mapping:

        1. If ``system_filter`` is set and does not match *system_id*, skip.
        2. Extract the claim value from *raw_claims* using ``claim_path``
           (supports dot notation).
        3. Apply ``transform`` if set.
        4. Emit ``target_header -> value``.

        Only mappings with ``target_type == "header"`` are included in the
        returned dict.  (Query-param mappings are intentionally omitted from
        this helper; they are handled separately at the request builder level.)
        """
        headers: dict[str, str] = {}
        for mapping in mappings:
            # 1. System filter
            if mapping.system_filter and mapping.system_filter != system_id:
                continue

            # 2. Extract claim
            value = _extract_claim(raw_claims, mapping.claim_path)
            if value is None:
                logger.debug(
                    "SSO claim %r not found in raw_claims; skipping mapping %s",
                    mapping.claim_path,
                    mapping.id,
                )
                continue

            # 3. Transform
            value = _apply_transform(value, mapping.transform)

            # 4. Emit header
            if mapping.target_type == "header":
                headers[mapping.target_header] = value

        return headers
