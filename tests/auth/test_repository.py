# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for OIDCProviderRepository CRUD operations."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydek.auth.repository import OIDCProviderRepository
from flydek.models.base import Base


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def encryption_key() -> str:
    """A valid Fernet key for testing encryption."""
    return Fernet.generate_key().decode()


@pytest.fixture
def repo(session_factory, encryption_key) -> OIDCProviderRepository:
    return OIDCProviderRepository(session_factory, encryption_key)


class TestOIDCProviderRepository:
    async def test_create_and_get_provider(self, repo: OIDCProviderRepository):
        """Create a provider and retrieve it by ID."""
        row = await repo.create_provider(
            provider_type="keycloak",
            display_name="Dev Keycloak",
            issuer_url="https://idp.example.com",
            client_id="my-client",
            client_secret="super-secret",
            tenant_id="tenant-1",
            scopes=["openid", "profile", "email"],
            roles_claim="realm_access.roles",
            permissions_claim="resource_access",
        )
        assert row.id is not None
        assert row.provider_type == "keycloak"
        assert row.display_name == "Dev Keycloak"
        assert row.issuer_url == "https://idp.example.com"
        assert row.client_id == "my-client"
        assert row.is_active is True

        # Retrieve by ID
        fetched = await repo.get_provider(row.id)
        assert fetched is not None
        assert fetched.display_name == "Dev Keycloak"

        # Decrypt the secret
        secret = repo.decrypt_secret(fetched)
        assert secret == "super-secret"

    async def test_list_providers(self, repo: OIDCProviderRepository):
        """list_providers() returns all persisted providers."""
        await repo.create_provider(
            provider_type="keycloak",
            display_name="Alpha",
            issuer_url="https://alpha.example.com",
            client_id="alpha-client",
        )
        await repo.create_provider(
            provider_type="google",
            display_name="Beta",
            issuer_url="https://accounts.google.com",
            client_id="beta-client",
        )

        providers = await repo.list_providers()
        assert len(providers) == 2
        names = [p.display_name for p in providers]
        assert "Alpha" in names
        assert "Beta" in names

    async def test_update_provider(self, repo: OIDCProviderRepository):
        """update_provider() modifies existing fields."""
        row = await repo.create_provider(
            provider_type="okta",
            display_name="Original",
            issuer_url="https://okta.example.com",
            client_id="okta-client",
            client_secret="old-secret",
        )

        updated = await repo.update_provider(
            row.id,
            display_name="Updated",
            client_secret="new-secret",
        )
        assert updated is not None
        assert updated.display_name == "Updated"

        # Verify the new secret
        secret = repo.decrypt_secret(updated)
        assert secret == "new-secret"

    async def test_delete_provider(self, repo: OIDCProviderRepository):
        """delete_provider() removes the provider from the database."""
        row = await repo.create_provider(
            provider_type="auth0",
            display_name="To Delete",
            issuer_url="https://auth0.example.com",
            client_id="auth0-client",
        )

        await repo.delete_provider(row.id)

        result = await repo.get_provider(row.id)
        assert result is None

    async def test_get_active_provider(self, repo: OIDCProviderRepository):
        """get_active_provider() returns the first active provider."""
        await repo.create_provider(
            provider_type="microsoft",
            display_name="Active One",
            issuer_url="https://login.microsoftonline.com",
            client_id="ms-client",
            is_active=True,
        )
        await repo.create_provider(
            provider_type="google",
            display_name="Inactive",
            issuer_url="https://accounts.google.com",
            client_id="goog-client",
            is_active=False,
        )

        active = await repo.get_active_provider()
        assert active is not None
        assert active.display_name == "Active One"

    async def test_parse_scopes(self, repo: OIDCProviderRepository):
        """parse_scopes() deserializes the JSON scopes column."""
        row = await repo.create_provider(
            provider_type="keycloak",
            display_name="With Scopes",
            issuer_url="https://idp.example.com",
            client_id="scoped-client",
            scopes=["openid", "profile", "email", "roles"],
        )

        scopes = repo.parse_scopes(row)
        assert scopes == ["openid", "profile", "email", "roles"]
