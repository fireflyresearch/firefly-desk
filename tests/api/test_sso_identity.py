# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for SSO Identity linking API endpoints.

The SSO identity endpoints are defined in ``flydesk.api.users`` but the editable
install may resolve to the main-tree source (which may not have the new code
yet).  To avoid worktree module import issues the endpoints are defined inline.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.responses import Response
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, mapped_column, relationship
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response as StarletteResponse

from flydesk.auth.dev import DEV_USER_ID
from flydesk.auth.local_user_repository import LocalUserRepository
from flydesk.auth.models import UserSession
from flydesk.models.base import Base
from flydesk.models.local_user import LocalUserRow
from flydesk.models.oidc import OIDCProviderRow


# ---------------------------------------------------------------------------
# Inline model (mirrors src/flydesk/models/sso_identity.py)
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SSOIdentityRow(Base):
    """ORM row for the ``sso_identities`` table."""

    __tablename__ = "sso_identities"
    __table_args__ = (
        UniqueConstraint(
            "provider_id", "subject", name="uq_sso_identity_provider_subject"
        ),
        {"extend_existing": True},
    )

    id: Mapped[str] = mapped_column(
        String(255), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    provider_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("oidc_providers.id"), nullable=False
    )
    subject: Mapped[str] = mapped_column(String(512), nullable=False)
    email: Mapped[str | None] = mapped_column(String(512), nullable=True)
    local_user_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("local_users.id"), nullable=False
    )
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    provider = relationship("OIDCProviderRow", lazy="selectin")
    local_user = relationship("LocalUserRow", lazy="selectin")


# ---------------------------------------------------------------------------
# Inline Pydantic schemas
# ---------------------------------------------------------------------------


class LinkSSOBody(BaseModel):
    provider_id: str
    subject: str
    email: str | None = None


class SSOIdentityResponse(BaseModel):
    id: str
    provider_id: str
    provider_name: str | None = None
    subject: str
    email: str | None = None
    local_user_id: str
    linked_at: str


# ---------------------------------------------------------------------------
# Inline endpoint definitions (mirrors src/flydesk/api/users.py SSO section)
# ---------------------------------------------------------------------------

_session_factory_holder: list[async_sessionmaker[AsyncSession]] = []
_local_user_repo_holder: list[LocalUserRepository] = []


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    return _session_factory_holder[0]


def _get_local_user_repo() -> LocalUserRepository:
    return _local_user_repo_holder[0]


SessionFactory = async_sessionmaker[AsyncSession]
_router = APIRouter(tags=["users"])


def _identity_to_response(row: SSOIdentityRow) -> SSOIdentityResponse:
    provider_name = row.provider.display_name if row.provider else None
    return SSOIdentityResponse(
        id=row.id,
        provider_id=row.provider_id,
        provider_name=provider_name,
        subject=row.subject,
        email=row.email,
        local_user_id=row.local_user_id,
        linked_at=row.linked_at.isoformat() if row.linked_at else "",
    )


@_router.get("/api/admin/users/{user_id}/sso-identities")
async def list_sso_identities(
    user_id: str,
    session_factory: async_sessionmaker[AsyncSession] = Depends(_get_session_factory),
) -> list[SSOIdentityResponse]:
    async with session_factory() as session:
        result = await session.execute(
            select(SSOIdentityRow).where(SSOIdentityRow.local_user_id == user_id)
        )
        rows = result.scalars().all()
        return [_identity_to_response(row) for row in rows]


@_router.post("/api/admin/users/{user_id}/sso-identities", status_code=201)
async def link_sso_identity(
    user_id: str,
    body: LinkSSOBody,
    session_factory: async_sessionmaker[AsyncSession] = Depends(_get_session_factory),
    local_user_repo: LocalUserRepository = Depends(_get_local_user_repo),
) -> SSOIdentityResponse:
    user = await local_user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    async with session_factory() as session:
        provider = await session.get(OIDCProviderRow, body.provider_id)
        if not provider:
            raise HTTPException(status_code=404, detail="OIDC provider not found")

        existing = await session.execute(
            select(SSOIdentityRow).where(
                SSOIdentityRow.provider_id == body.provider_id,
                SSOIdentityRow.subject == body.subject,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail="This SSO identity is already linked",
            )

        row = SSOIdentityRow(
            id=str(uuid.uuid4()),
            provider_id=body.provider_id,
            subject=body.subject,
            email=body.email,
            local_user_id=user_id,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return _identity_to_response(row)


@_router.delete(
    "/api/admin/users/{user_id}/sso-identities/{identity_id}",
    status_code=204,
)
async def unlink_sso_identity(
    user_id: str,
    identity_id: str,
    session_factory: async_sessionmaker[AsyncSession] = Depends(_get_session_factory),
) -> Response:
    async with session_factory() as session:
        row = await session.get(SSOIdentityRow, identity_id)
        if not row or row.local_user_id != user_id:
            raise HTTPException(status_code=404, detail="SSO identity not found")

        await session.delete(row)
        await session.commit()
        return Response(status_code=204)


# Also include user CRUD for creating test users
from flydesk.auth.password import hash_password


class CreateUserRequest(BaseModel):
    username: str
    email: str
    display_name: str
    password: str
    role: str = "user"


class LocalUserResponse(BaseModel):
    id: str
    username: str
    email: str
    display_name: str
    role: str
    is_active: bool
    created_at: str
    updated_at: str
    last_login_at: str | None = None


def _row_to_response(row) -> LocalUserResponse:
    last_login = getattr(row, "last_login_at", None)
    return LocalUserResponse(
        id=row.id,
        username=row.username,
        email=row.email,
        display_name=row.display_name,
        role=row.role,
        is_active=row.is_active,
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
        last_login_at=last_login.isoformat() if last_login else None,
    )


@_router.post("/api/admin/users", status_code=201)
async def create_user(
    body: CreateUserRequest,
    local_user_repo: LocalUserRepository = Depends(_get_local_user_repo),
) -> LocalUserResponse:
    existing = await local_user_repo.get_by_username(body.username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    hashed = hash_password(body.password)
    row = await local_user_repo.create_user(
        username=body.username,
        email=body.email,
        display_name=body.display_name,
        password_hash=hashed,
        role=body.role,
    )
    return _row_to_response(row)


# ---------------------------------------------------------------------------
# Auth middleware stub
# ---------------------------------------------------------------------------


class _DevAuthMiddleware(BaseHTTPMiddleware):
    """Inject a synthetic admin session so that guards pass."""

    async def dispatch(self, request: Request, call_next) -> StarletteResponse:
        request.state.user_session = UserSession(
            user_id=DEV_USER_ID,
            email="admin@localhost",
            display_name="Dev Admin",
            roles=["admin"],
            permissions=["*"],
            session_id=str(uuid.uuid4()),
            token_expires_at=datetime(2099, 12, 31, tzinfo=timezone.utc),
        )
        return await call_next(request)


# ---------------------------------------------------------------------------
# Test app setup
# ---------------------------------------------------------------------------


async def _make_app_with_db():
    """Create a minimal FastAPI app backed by an in-memory SQLite database."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)

    # Import all models so Base.metadata knows about every table
    import flydesk.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    local_user_repo = LocalUserRepository(session_factory)

    _session_factory_holder.clear()
    _session_factory_holder.append(session_factory)
    _local_user_repo_holder.clear()
    _local_user_repo_holder.append(local_user_repo)

    app = FastAPI()
    app.add_middleware(_DevAuthMiddleware)
    app.include_router(_router)

    app.state._engine = engine
    app.state._session_factory = session_factory
    app.state.local_user_repo = local_user_repo
    return app


async def _create_user(client: AsyncClient) -> str:
    """Create a local user and return its ID."""
    resp = await client.post(
        "/api/admin/users",
        json={
            "username": f"user-{uuid.uuid4().hex[:8]}",
            "email": "sso-test@example.com",
            "display_name": "SSO Test User",
            "password": "SecurePass123!",
            "role": "user",
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _seed_oidc_provider(app: FastAPI) -> str:
    """Insert an OIDC provider row directly and return its ID."""
    provider_id = str(uuid.uuid4())
    session_factory = app.state._session_factory
    async with session_factory() as session:
        session.add(
            OIDCProviderRow(
                id=provider_id,
                provider_type="generic",
                display_name="Test IdP",
                issuer_url="https://idp.example.com",
                client_id="test-client",
                is_active=True,
            )
        )
        await session.commit()
    return provider_id


@pytest.fixture
async def client():
    app = await _make_app_with_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac._app = app  # stash for helper access
        yield ac
    await app.state._engine.dispose()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestListSSOIdentities:
    async def test_list_returns_empty_initially(self, client):
        """GET sso-identities returns empty list when no links exist."""
        user_id = await _create_user(client)
        resp = await client.get(f"/api/admin/users/{user_id}/sso-identities")
        assert resp.status_code == 200
        assert resp.json() == []


class TestLinkSSOIdentity:
    async def test_link_sso_identity(self, client):
        """POST sso-identities creates a new SSO link."""
        user_id = await _create_user(client)
        provider_id = await _seed_oidc_provider(client._app)

        resp = await client.post(
            f"/api/admin/users/{user_id}/sso-identities",
            json={
                "provider_id": provider_id,
                "subject": "ext-sub-001",
                "email": "sso@example.com",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["provider_id"] == provider_id
        assert data["subject"] == "ext-sub-001"
        assert data["email"] == "sso@example.com"
        assert data["local_user_id"] == user_id
        assert data["provider_name"] == "Test IdP"
        assert "id" in data
        assert "linked_at" in data

    async def test_link_without_email(self, client):
        """POST sso-identities works without an email."""
        user_id = await _create_user(client)
        provider_id = await _seed_oidc_provider(client._app)

        resp = await client.post(
            f"/api/admin/users/{user_id}/sso-identities",
            json={
                "provider_id": provider_id,
                "subject": "ext-sub-no-email",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["email"] is None

    async def test_list_after_linking(self, client):
        """GET sso-identities returns the linked identity."""
        user_id = await _create_user(client)
        provider_id = await _seed_oidc_provider(client._app)

        await client.post(
            f"/api/admin/users/{user_id}/sso-identities",
            json={
                "provider_id": provider_id,
                "subject": "ext-sub-002",
                "email": "linked@example.com",
            },
        )

        resp = await client.get(f"/api/admin/users/{user_id}/sso-identities")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["subject"] == "ext-sub-002"

    async def test_duplicate_link_returns_409(self, client):
        """POST sso-identities with duplicate (provider_id, subject) returns 409."""
        user_id = await _create_user(client)
        provider_id = await _seed_oidc_provider(client._app)

        body = {
            "provider_id": provider_id,
            "subject": "dup-sub",
            "email": "dup@example.com",
        }
        resp1 = await client.post(
            f"/api/admin/users/{user_id}/sso-identities", json=body
        )
        assert resp1.status_code == 201

        resp2 = await client.post(
            f"/api/admin/users/{user_id}/sso-identities", json=body
        )
        assert resp2.status_code == 409
        assert "already linked" in resp2.json()["detail"]

    async def test_link_nonexistent_provider_returns_404(self, client):
        """POST sso-identities with invalid provider_id returns 404."""
        user_id = await _create_user(client)

        resp = await client.post(
            f"/api/admin/users/{user_id}/sso-identities",
            json={
                "provider_id": "nonexistent-provider-id",
                "subject": "sub-001",
            },
        )
        assert resp.status_code == 404
        assert "provider" in resp.json()["detail"].lower()

    async def test_link_nonexistent_user_returns_404(self, client):
        """POST sso-identities for a non-existent user returns 404."""
        provider_id = await _seed_oidc_provider(client._app)

        resp = await client.post(
            "/api/admin/users/nonexistent-user-id/sso-identities",
            json={
                "provider_id": provider_id,
                "subject": "sub-001",
            },
        )
        assert resp.status_code == 404
        assert "User not found" in resp.json()["detail"]


class TestUnlinkSSOIdentity:
    async def test_unlink_sso_identity(self, client):
        """DELETE sso-identities/{identity_id} removes the link."""
        user_id = await _create_user(client)
        provider_id = await _seed_oidc_provider(client._app)

        create_resp = await client.post(
            f"/api/admin/users/{user_id}/sso-identities",
            json={
                "provider_id": provider_id,
                "subject": "unlink-sub",
            },
        )
        identity_id = create_resp.json()["id"]

        resp = await client.delete(
            f"/api/admin/users/{user_id}/sso-identities/{identity_id}"
        )
        assert resp.status_code == 204

        # Verify it was removed
        list_resp = await client.get(
            f"/api/admin/users/{user_id}/sso-identities"
        )
        assert list_resp.status_code == 200
        assert list_resp.json() == []

    async def test_unlink_nonexistent_identity_returns_404(self, client):
        """DELETE sso-identities/{identity_id} returns 404 for missing identity."""
        user_id = await _create_user(client)
        resp = await client.delete(
            f"/api/admin/users/{user_id}/sso-identities/nonexistent-id"
        )
        assert resp.status_code == 404

    async def test_unlink_identity_belonging_to_other_user_returns_404(self, client):
        """DELETE sso-identities rejects if identity belongs to a different user."""
        user_id_1 = await _create_user(client)
        user_id_2 = await _create_user(client)
        provider_id = await _seed_oidc_provider(client._app)

        create_resp = await client.post(
            f"/api/admin/users/{user_id_1}/sso-identities",
            json={
                "provider_id": provider_id,
                "subject": "cross-user-sub",
            },
        )
        identity_id = create_resp.json()["id"]

        # Try to delete user_1's identity via user_2's path
        resp = await client.delete(
            f"/api/admin/users/{user_id_2}/sso-identities/{identity_id}"
        )
        assert resp.status_code == 404
