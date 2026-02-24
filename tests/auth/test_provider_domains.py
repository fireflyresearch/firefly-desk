# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for allowed_email_domains on OIDC provider CRUD."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.auth.repository import OIDCProviderRepository, _from_json
from flydesk.models.base import Base


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
    return Fernet.generate_key().decode()


@pytest.fixture
def repo(session_factory, encryption_key) -> OIDCProviderRepository:
    return OIDCProviderRepository(session_factory, encryption_key)


class TestAllowedEmailDomains:
    """CRUD tests for the allowed_email_domains field."""

    async def test_create_with_allowed_domains(self, repo: OIDCProviderRepository):
        """Creating a provider with allowed_email_domains persists the list."""
        domains = ["mycompany.com", "partner.org"]
        row = await repo.create_provider(
            provider_type="keycloak",
            display_name="Domain-Restricted",
            issuer_url="https://idp.example.com",
            client_id="client-1",
            allowed_email_domains=domains,
        )
        assert row.allowed_email_domains is not None
        parsed = _from_json(row.allowed_email_domains)
        assert parsed == ["mycompany.com", "partner.org"]

    async def test_create_without_domains(self, repo: OIDCProviderRepository):
        """Creating a provider without allowed_email_domains stores None (all allowed)."""
        row = await repo.create_provider(
            provider_type="google",
            display_name="Open Provider",
            issuer_url="https://accounts.google.com",
            client_id="client-2",
        )
        assert row.allowed_email_domains is None

    async def test_update_add_domains(self, repo: OIDCProviderRepository):
        """Updating a provider to add allowed_email_domains persists the change."""
        row = await repo.create_provider(
            provider_type="okta",
            display_name="Initially Open",
            issuer_url="https://okta.example.com",
            client_id="client-3",
        )
        assert row.allowed_email_domains is None

        updated = await repo.update_provider(
            row.id,
            allowed_email_domains=["restricted.com"],
        )
        assert updated is not None
        parsed = _from_json(updated.allowed_email_domains)
        assert parsed == ["restricted.com"]

    async def test_update_remove_domains(self, repo: OIDCProviderRepository):
        """Updating allowed_email_domains to None removes the restriction."""
        row = await repo.create_provider(
            provider_type="auth0",
            display_name="Was Restricted",
            issuer_url="https://auth0.example.com",
            client_id="client-4",
            allowed_email_domains=["locked.com"],
        )
        parsed = _from_json(row.allowed_email_domains)
        assert parsed == ["locked.com"]

        updated = await repo.update_provider(
            row.id,
            allowed_email_domains=None,
        )
        assert updated is not None
        assert updated.allowed_email_domains is None

    async def test_domains_round_trip(self, repo: OIDCProviderRepository):
        """Domains survive a create -> read -> verify round-trip."""
        domains = ["alpha.com", "beta.org", "gamma.io"]
        row = await repo.create_provider(
            provider_type="microsoft",
            display_name="Round-Trip Test",
            issuer_url="https://login.microsoftonline.com",
            client_id="client-5",
            allowed_email_domains=domains,
        )

        fetched = await repo.get_provider(row.id)
        assert fetched is not None
        parsed = _from_json(fetched.allowed_email_domains)
        assert parsed == ["alpha.com", "beta.org", "gamma.io"]

    async def test_domains_coexist_with_scopes(self, repo: OIDCProviderRepository):
        """Both scopes and allowed_email_domains can be set independently."""
        row = await repo.create_provider(
            provider_type="keycloak",
            display_name="Both Fields",
            issuer_url="https://idp.example.com",
            client_id="client-6",
            scopes=["openid", "profile"],
            allowed_email_domains=["company.com"],
        )
        scopes = _from_json(row.scopes)
        domains = _from_json(row.allowed_email_domains)
        assert scopes == ["openid", "profile"]
        assert domains == ["company.com"]
