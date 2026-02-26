# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for CatalogRepository."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.catalog.enums import AuthType, HttpMethod, RiskLevel, SystemStatus
from flydesk.catalog.models import AuthConfig, ExternalSystem, ServiceEndpoint
from flydesk.catalog.repository import CatalogRepository
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
def repo(session_factory):
    return CatalogRepository(session_factory)


@pytest.fixture
def sample_system() -> ExternalSystem:
    return ExternalSystem(
        id="crm-test",
        name="Test CRM",
        description="A test CRM system",
        base_url="https://api.test.com",
        auth_config=AuthConfig(auth_type=AuthType.API_KEY, credential_id="cred-1"),
        tags=["crm"],
        status=SystemStatus.ACTIVE,
    )


@pytest.fixture
def sample_endpoint() -> ServiceEndpoint:
    return ServiceEndpoint(
        id="get-customer",
        system_id="crm-test",
        name="Get Customer",
        description="Get a customer by ID",
        method=HttpMethod.GET,
        path="/customers/{id}",
        when_to_use="When asked about a customer",
        risk_level=RiskLevel.READ,
        required_permissions=["customers:read"],
    )


class TestCatalogRepository:
    async def test_create_and_get_system(self, repo, sample_system):
        await repo.create_system(sample_system)
        result = await repo.get_system("crm-test")
        assert result is not None
        assert result.name == "Test CRM"
        assert result.auth_config.auth_type == AuthType.API_KEY

    async def test_get_system_not_found(self, repo):
        result = await repo.get_system("nonexistent")
        assert result is None

    async def test_list_systems(self, repo, sample_system):
        await repo.create_system(sample_system)
        systems, total = await repo.list_systems()
        assert len(systems) == 1
        assert total == 1
        assert systems[0].id == "crm-test"

    async def test_update_system(self, repo, sample_system):
        await repo.create_system(sample_system)
        sample_system.name = "Updated CRM"
        await repo.update_system(sample_system)
        result = await repo.get_system("crm-test")
        assert result is not None
        assert result.name == "Updated CRM"

    async def test_delete_system(self, repo, sample_system):
        await repo.create_system(sample_system)
        await repo.delete_system("crm-test")
        result = await repo.get_system("crm-test")
        assert result is None

    async def test_create_and_get_endpoint(self, repo, sample_system, sample_endpoint):
        await repo.create_system(sample_system)
        await repo.create_endpoint(sample_endpoint)
        result = await repo.get_endpoint("get-customer")
        assert result is not None
        assert result.risk_level == RiskLevel.READ

    async def test_list_endpoints_by_system(self, repo, sample_system, sample_endpoint):
        await repo.create_system(sample_system)
        await repo.create_endpoint(sample_endpoint)
        endpoints = await repo.list_endpoints(system_id="crm-test")
        assert len(endpoints) == 1

    async def test_list_all_active_endpoints(self, repo, sample_system, sample_endpoint):
        await repo.create_system(sample_system)
        await repo.create_endpoint(sample_endpoint)
        endpoints = await repo.list_active_endpoints()
        assert len(endpoints) == 1
        assert endpoints[0].system_id == "crm-test"
