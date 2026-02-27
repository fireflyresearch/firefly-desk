# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Auth API -- OIDC login flow, local login, logout, and provider listing."""

from __future__ import annotations

import json
import logging
import secrets
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel

from flydesk.api.deps import get_audit_logger, get_local_user_repo, get_oidc_client, get_oidc_repo
from flydesk.audit.logger import AuditLogger
from flydesk.audit.models import AuditEvent, AuditEventType
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

AuditLog = Annotated[AuditLogger, Depends(get_audit_logger)]
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
# Helpers
# ---------------------------------------------------------------------------


def _parse_domains(raw: Any) -> set[str]:
    """Parse ``allowed_email_domains`` from DB into a set of lowercase domains.

    The column may be ``None``, a JSON string (SQLite/Text backend), or an
    already-decoded list (Postgres JSONB).  Returns an empty set when the
    value is ``None`` or empty, which means *all* domains are allowed.
    """
    if not raw:
        return set()
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return set()
    if not isinstance(raw, (list, tuple, set)):
        return set()
    return {d.lower().strip() for d in raw if isinstance(d, str) and d.strip()}


def _extract_email_from_id_token(id_token_raw: str | None) -> str | None:
    """Decode an id_token (without verification) to extract the email claim.

    This is a *fast-path* check; the id_token has already been validated
    by the OIDC provider during the code exchange.  We only peek at the
    payload to get the email for domain filtering.
    """
    if not id_token_raw:
        return None
    try:
        import base64

        # JWT = header.payload.signature — we only need the payload.
        parts = id_token_raw.split(".")
        if len(parts) < 2:
            return None
        # Add padding to handle missing base64 padding
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get("email")
    except Exception:
        return None


def _check_email_domain(
    email: str | None,
    allowed_domains: set[str],
    *,
    context: str = "userinfo",
) -> None:
    """Raise HTTPException(403) if the email domain is not in the allowed set.

    When *allowed_domains* is empty the check is a no-op (all domains allowed).
    When *email* is falsy the check is also a no-op (gracefully allow missing email).
    """
    if not allowed_domains:
        return  # No restriction configured
    if not email:
        return  # No email to check — allow through

    domain = email.rsplit("@", 1)[-1].lower() if "@" in email else ""
    if not domain:
        return  # Malformed email with no domain — allow through

    if domain not in allowed_domains:
        raise HTTPException(
            status_code=403,
            detail=f"Email domain '{domain}' is not allowed for this SSO provider",
        )


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
    audit: AuditLog,
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

    # -- Email domain filtering -----------------------------------------
    allowed_domains = _parse_domains(row.allowed_email_domains)

    # Fast path: check email from id_token claims (avoids userinfo round-trip
    # when the domain is blocked).
    if allowed_domains and id_token:
        id_email = _extract_email_from_id_token(id_token)
        if id_email:
            _check_email_domain(id_email, allowed_domains, context="id_token")

    # Fetch userinfo
    user_info: dict[str, Any] = {}
    try:
        user_info = await oidc_client.get_userinfo(access_token)
    except Exception:
        logger.debug("Userinfo fetch failed (non-fatal).", exc_info=True)

    # Check email domain from userinfo (authoritative source).
    if allowed_domains:
        userinfo_email = (user_info.get("email", "") or "")
        _check_email_domain(userinfo_email, allowed_domains, context="userinfo")

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

    # Audit: log successful SSO login
    sso_email = user_info.get("email", "") or _extract_email_from_id_token(id_token) or "unknown"
    client_ip = request.client.host if request.client else "unknown"
    await audit.log(
        AuditEvent(
            event_type=AuditEventType.AUTH_LOGIN,
            user_id=sso_email,
            action="auth_login",
            detail={"method": "sso", "ip": client_ip, "success": True},
            ip_address=client_ip,
        )
    )

    return CallbackResponse(
        access_token=access_token,
        id_token=id_token,
        expires_in=expires_in,
        user_info=user_info,
    )


@router.post("/login", response_model=LocalLoginResponse)
async def local_login(
    request: Request,
    body: LocalLoginRequest,
    response: Response,
    audit: AuditLog,
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

    # Audit: log successful local login
    client_ip = request.client.host if request.client else "unknown"
    await audit.log(
        AuditEvent(
            event_type=AuditEventType.AUTH_LOGIN,
            user_id=user.email or body.username,
            action="auth_login",
            detail={"method": "local", "ip": client_ip, "success": True},
            ip_address=client_ip,
        )
    )

    return LocalLoginResponse(access_token=token)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    audit: AuditLog,
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

    # Audit: log logout
    user_session = getattr(request.state, "user_session", None)
    user_id = user_session.user_id if user_session else "anonymous"
    client_ip = request.client.host if request.client else "unknown"
    await audit.log(
        AuditEvent(
            event_type=AuditEventType.AUTH_LOGOUT,
            user_id=user_id,
            action="auth_logout",
            detail={"ip": client_ip},
            ip_address=client_ip,
        )
    )

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
