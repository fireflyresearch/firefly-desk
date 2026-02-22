# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""JWT authentication middleware for FastAPI."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from flydek.auth.models import UserSession

# Paths that don't require authentication
PUBLIC_PATHS = frozenset({"/api/health", "/docs", "/openapi.json", "/redoc"})


class AuthMiddleware(BaseHTTPMiddleware):
    """Extract and validate JWT from Authorization header."""

    def __init__(
        self,
        app: Any,
        *,
        roles_claim: str = "roles",
        permissions_claim: str = "permissions",
        token_decoder: Callable[[str], dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(app)
        self._roles_claim = roles_claim
        self._permissions_claim = permissions_claim
        self._token_decoder = token_decoder

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        """Process each request, enforcing JWT auth on non-public paths."""
        # Skip auth for public paths
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid Authorization header"},
            )

        token = auth_header[7:]  # Strip "Bearer "
        try:
            claims = self._decode_token(token)
        except Exception:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"},
            )

        # Build UserSession from claims
        session = UserSession(
            user_id=claims.get("sub", ""),
            email=claims.get("email", ""),
            display_name=claims.get("name", claims.get("email", "")),
            roles=self._extract_claim(claims, self._roles_claim),
            permissions=self._extract_claim(claims, self._permissions_claim),
            tenant_id=claims.get("tenant_id"),
            session_id=str(uuid.uuid4()),
            token_expires_at=datetime.fromtimestamp(
                claims.get("exp", 0), tz=timezone.utc
            ),
            raw_claims=claims,
        )

        request.state.user_session = session
        return await call_next(request)

    def _decode_token(self, token: str) -> dict[str, Any]:
        """Decode the JWT token using the configured decoder."""
        if self._token_decoder:
            return self._token_decoder(token)
        raise NotImplementedError("No token decoder configured")

    @staticmethod
    def _extract_claim(claims: dict[str, Any], claim_path: str) -> list[str]:
        """Extract a claim value, supporting dot-notation paths."""
        parts = claim_path.split(".")
        value: Any = claims
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [value]
        return []
