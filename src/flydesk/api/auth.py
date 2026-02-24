# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Auth API -- OIDC login flow, local login, logout, and provider listing."""

from __future__ import annotations

import logging
import secrets
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel

from flydesk.auth.oidc import OIDCClient, generate_pkce_pair
from flydesk.auth.providers import get_provider as get_provider_profile
from flydesk.auth.repository import OIDCProviderRepository
from flydesk.config import get_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ProviderInfo(BaseModel):
    """Public info about an OIDC provider."""

    id: str
    provider_type: str
    display_name: str
    issuer_url: str


class LoginUrlResponse(BaseModel):
    """Response containing the authorization URL."""

    login_url: str
    state: str


class CallbackResponse(BaseModel):
    """Response after successful code exchange."""

    access_token: str
    id_token: str | None = None
    token_type: str = "Bearer"
    expires_in: int | None = None
    user_info: dict[str, Any] = {}


class UserInfoResponse(BaseModel):
    """User info fetched from the OIDC provider."""

    claims: dict[str, Any]


class LocalLoginRequest(BaseModel):
    """Credentials for local (username + password) authentication."""

    username: str
    password: str


class LocalLoginResponse(BaseModel):
    """Response after successful local login."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 86400


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_local_user_repo():
    """Provide a LocalUserRepository instance.

    In production this is wired in the lifespan.
    """
    raise NotImplementedError(
        "get_local_user_repo must be overridden via app.dependency_overrides"
    )


def get_oidc_repo() -> OIDCProviderRepository:
    """Provide an OIDCProviderRepository instance.

    In production this is wired in the lifespan.
    """
    raise NotImplementedError(
        "get_oidc_repo must be overridden via app.dependency_overrides"
    )


def get_oidc_client() -> OIDCClient | None:
    """Provide a default OIDCClient configured from env.

    Returns ``None`` when no issuer URL is configured.
    """
    return None


OIDCRepo = Annotated[OIDCProviderRepository, Depends(get_oidc_repo)]


# ---------------------------------------------------------------------------
# In-memory PKCE / state store (per-process; suitable for single-instance).
# A production deployment should use Redis or DB-backed sessions.
# ---------------------------------------------------------------------------

_MAX_PENDING_STATES = 10_000
_STATE_TTL_SECONDS = 600  # 10 minutes

_pending_states: dict[str, dict[str, str | float]] = {}


def _store_state(state: str, data: dict[str, str]) -> None:
    """Store a state entry with a timestamp, evicting stale/overflow entries."""
    import time

    now = time.time()

    # Evict expired entries on every insert.
    expired = [k for k, v in _pending_states.items() if now - v.get("_ts", 0) > _STATE_TTL_SECONDS]
    for k in expired:
        _pending_states.pop(k, None)

    # Evict oldest entries if still over capacity.
    if len(_pending_states) >= _MAX_PENDING_STATES:
        sorted_keys = sorted(_pending_states, key=lambda k: _pending_states[k].get("_ts", 0))
        for k in sorted_keys[: len(sorted_keys) // 2]:
            _pending_states.pop(k, None)

    _pending_states[state] = {**data, "_ts": now}


def _pop_state(state: str) -> dict[str, str] | None:
    """Pop a state entry if it exists and is not expired."""
    import time

    entry = _pending_states.pop(state, None)
    if entry is None:
        return None
    ts = entry.pop("_ts", 0)
    if time.time() - ts > _STATE_TTL_SECONDS:
        return None  # Expired
    return {k: v for k, v in entry.items() if isinstance(v, str)}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/providers", response_model=list[ProviderInfo])
async def list_providers(repo: OIDCRepo) -> list[ProviderInfo]:
    """List all configured OIDC providers (public endpoint)."""
    rows = await repo.list_providers()
    return [
        ProviderInfo(
            id=row.id,
            provider_type=row.provider_type,
            display_name=row.display_name,
            issuer_url=row.issuer_url,
        )
        for row in rows
        if row.is_active
    ]


@router.get("/login-url", response_model=LoginUrlResponse)
async def get_login_url(
    repo: OIDCRepo,
    provider_id: str = Query(..., description="ID of the OIDC provider to use"),
    redirect_uri: str = Query("", description="Post-login redirect URI"),
) -> LoginUrlResponse:
    """Generate an authorization URL for the specified OIDC provider.

    Creates a unique ``state`` token and optional PKCE challenge, then returns
    the full authorization URL that the frontend should redirect the user to.
    """
    row = await repo.get_provider(provider_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Provider not found")

    config = get_config()
    effective_redirect = redirect_uri or config.oidc_redirect_uri

    client_secret = repo.decrypt_secret(row)
    oidc_client = OIDCClient(
        issuer_url=row.issuer_url,
        client_id=row.client_id,
        client_secret=client_secret or "",
    )

    # Fetch discovery so we can build the URL synchronously
    discovery = await oidc_client.discover()

    # Determine scopes
    scopes = repo.parse_scopes(row) or config.oidc_scopes

    # PKCE
    profile = get_provider_profile(row.provider_type)
    code_verifier: str | None = None
    code_challenge: str | None = None
    if profile.supports_pkce:
        code_verifier, code_challenge = generate_pkce_pair()

    state = secrets.token_urlsafe(32)
    _store_state(state, {
        "provider_id": provider_id,
        "redirect_uri": effective_redirect,
        "code_verifier": code_verifier or "",
    })

    login_url = oidc_client.build_auth_url(
        redirect_uri=effective_redirect,
        state=state,
        scopes=scopes,
        code_challenge=code_challenge,
        discovery_doc=discovery,
    )

    return LoginUrlResponse(login_url=login_url, state=state)


@router.post("/callback", response_model=CallbackResponse)
async def auth_callback(
    request: Request,
    repo: OIDCRepo,
    response: Response,
) -> CallbackResponse:
    """Exchange an authorization code for tokens and set a session cookie.

    Expects a JSON body with ``code`` and ``state`` fields.
    """
    body = await request.json()
    code: str = body.get("code", "")
    state: str = body.get("state", "")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    pending = _pop_state(state)
    if pending is None:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    provider_id = pending["provider_id"]
    redirect_uri = pending["redirect_uri"]
    code_verifier = pending.get("code_verifier") or None

    row = await repo.get_provider(provider_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Provider not found")

    client_secret = repo.decrypt_secret(row)
    oidc_client = OIDCClient(
        issuer_url=row.issuer_url,
        client_id=row.client_id,
        client_secret=client_secret or "",
    )

    try:
        tokens = await oidc_client.exchange_code(
            code=code,
            redirect_uri=redirect_uri,
            code_verifier=code_verifier,
        )
    except Exception as exc:
        logger.exception("Token exchange failed")
        raise HTTPException(status_code=502, detail="Token exchange failed") from exc

    access_token = tokens.get("access_token", "")
    id_token = tokens.get("id_token")
    expires_in = tokens.get("expires_in")

    # Fetch userinfo
    user_info: dict[str, Any] = {}
    try:
        user_info = await oidc_client.get_userinfo(access_token)
    except Exception:
        logger.debug("Userinfo fetch failed (non-fatal).", exc_info=True)

    # Set a session cookie with the access token
    response.set_cookie(
        key="flydesk_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=expires_in or 3600,
        path="/",
    )

    return CallbackResponse(
        access_token=access_token,
        id_token=id_token,
        expires_in=expires_in,
        user_info=user_info,
    )


@router.post("/login", response_model=LocalLoginResponse)
async def local_login(
    body: LocalLoginRequest,
    response: Response,
    local_user_repo=Depends(get_local_user_repo),
) -> LocalLoginResponse:
    """Authenticate with a local username and password.

    On success, issues a locally-signed JWT and sets a session cookie.
    """
    from flydesk.auth.jwt_local import create_local_jwt
    from flydesk.auth.password import verify_password

    user = await local_user_repo.get_by_username(body.username)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    config = get_config()
    token = create_local_jwt(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        roles=[user.role],
        secret_key=config.effective_jwt_secret,
    )

    response.set_cookie(
        key="flydesk_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=86400,
        path="/",
    )

    return LocalLoginResponse(access_token=token)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    oidc_client_dep: OIDCClient | None = Depends(get_oidc_client),
) -> dict[str, str]:
    """Clear the session cookie and optionally revoke the token.

    If an ``end_session_endpoint`` is available, the client should redirect
    the user to it after calling this endpoint.
    """
    end_session_url: str | None = None
    if oidc_client_dep is not None:
        try:
            discovery = await oidc_client_dep.discover()
            end_session_url = discovery.end_session_endpoint or None
        except Exception:
            logger.debug("Discovery failed during logout (non-fatal).", exc_info=True)

    response.delete_cookie(key="flydesk_token", path="/")

    result: dict[str, str] = {"status": "logged_out"}
    if end_session_url:
        result["end_session_url"] = end_session_url
    return result


@router.get("/userinfo", response_model=UserInfoResponse)
async def get_userinfo(
    request: Request,
    oidc_client_dep: OIDCClient | None = Depends(get_oidc_client),
) -> UserInfoResponse:
    """Proxy the OIDC userinfo endpoint for the authenticated user."""
    # Extract token from header or cookie
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = request.cookies.get("flydesk_token", "")

    if not token:
        raise HTTPException(status_code=401, detail="No token available")

    if oidc_client_dep is None:
        raise HTTPException(status_code=501, detail="OIDC not configured")

    try:
        claims = await oidc_client_dep.get_userinfo(token)
    except Exception as exc:
        logger.exception("Userinfo fetch failed")
        raise HTTPException(status_code=502, detail="Userinfo fetch failed") from exc

    return UserInfoResponse(claims=claims)
