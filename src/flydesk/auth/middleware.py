# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""JWT authentication middleware for FastAPI."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from flydesk.auth.models import UserSession

if TYPE_CHECKING:
    from flydesk.auth.oidc import OIDCClient
    from flydesk.auth.providers import OIDCProviderProfile

logger = logging.getLogger(__name__)

# Path prefixes that don't require authentication.
# Uses prefix matching so sub-paths (e.g. /docs/oauth2-redirect) are also public.
PUBLIC_PATH_PREFIXES = (
    "/api/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/auth/providers",
    "/api/auth/login-url",
    "/api/auth/callback",
    "/api/auth/logout",
    "/api/auth/login",
    "/api/setup/create-admin",
)


class AuthMiddleware(BaseHTTPMiddleware):
    """Extract and validate JWT from Authorization header or cookie."""

    def __init__(
        self,
        app: Any,
        *,
        roles_claim: str = "roles",
        permissions_claim: str = "permissions",
        token_decoder: Callable[[str], dict[str, Any]] | None = None,
        oidc_client: OIDCClient | None = None,
        provider_profile: OIDCProviderProfile | None = None,
        local_jwt_secret: str | None = None,
    ) -> None:
        super().__init__(app)
        self._roles_claim = roles_claim
        self._permissions_claim = permissions_claim
        self._token_decoder = token_decoder
        self._oidc_client = oidc_client
        self._provider_profile = provider_profile
        self._local_jwt_secret = local_jwt_secret

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        """Process each request, enforcing JWT auth on non-public paths."""
        # Skip auth for public paths (prefix match)
        if any(request.url.path.startswith(p) for p in PUBLIC_PATH_PREFIXES):
            return await call_next(request)

        # Try Authorization header first, then cookie
        auth_header = request.headers.get("authorization", "")
        token: str | None = None

        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            token = request.cookies.get("flydesk_token")

        if not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid Authorization header"},
            )

        try:
            claims = await self._decode_token(token)
        except Exception:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"},
            )

        # Extract provider-specific claims if provider profile is available
        extra: dict[str, Any] = {}
        if self._provider_profile is not None:
            from flydesk.auth.providers import extract_user_claims

            extra = extract_user_claims(claims, self._provider_profile)

        # Build UserSession from claims
        session = UserSession(
            user_id=claims.get("sub", ""),
            email=claims.get("email", ""),
            display_name=claims.get("name", claims.get("email", "")),
            roles=extra.get("roles") or self._extract_claim(claims, self._roles_claim),
            permissions=(
                extra.get("permissions")
                or self._extract_claim(claims, self._permissions_claim)
            ),
            tenant_id=claims.get("tenant_id"),
            picture_url=extra.get("picture_url"),
            department=extra.get("department"),
            title=extra.get("title"),
            session_id=str(uuid.uuid4()),
            token_expires_at=datetime.fromtimestamp(
                claims.get("exp", 0), tz=timezone.utc
            ),
            raw_claims=claims,
        )

        # Resolve OIDC roles to local permissions and access scopes via RoleRepository
        role_repo = getattr(request.app.state, "role_repo", None)
        if role_repo is not None:
            resolved = await role_repo.get_permissions_for_roles(session.roles)
            access_scopes = await role_repo.get_access_scopes_for_roles(session.roles)
            session = session.model_copy(
                update={"permissions": resolved, "access_scopes": access_scopes},
            )

        request.state.user_session = session
        return await call_next(request)

    async def _decode_token(self, token: str) -> dict[str, Any]:
        """Decode the JWT token, routing by algorithm.

        * **HS256 + no ``kid``** -- local JWT, decoded with the configured
          ``local_jwt_secret``.
        * **RS256/ES256 + ``kid``** -- OIDC JWT, validated via the OIDC client
          or the legacy ``token_decoder`` callable.
        """
        import jwt as pyjwt

        try:
            header = pyjwt.get_unverified_header(token)
        except Exception:
            raise pyjwt.exceptions.InvalidTokenError("Invalid JWT header")

        # Local JWT: HS256, no kid
        if header.get("alg") == "HS256" and not header.get("kid"):
            if self._local_jwt_secret:
                from flydesk.auth.jwt_local import decode_local_jwt

                return decode_local_jwt(token, self._local_jwt_secret)
            raise NotImplementedError("Local JWT secret not configured")

        # OIDC JWT: has kid, RS256/ES256
        if self._oidc_client is not None:
            return await self._oidc_client.validate_token(token)
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
