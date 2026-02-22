# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for Catalog ORM models."""

from __future__ import annotations

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from flydek.models.base import Base
from flydek.models.catalog import CredentialRow, ExternalSystemRow, ServiceEndpointRow


class TestCatalogORM:
    @pytest.fixture
    async def engine(self):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield engine
        await engine.dispose()

    async def test_tables_created(self, engine):
        async with engine.connect() as conn:
            tables = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )
        assert "external_systems" in tables
        assert "service_endpoints" in tables
        assert "credentials" in tables

    def test_system_row_has_expected_columns(self):
        columns = {c.name for c in ExternalSystemRow.__table__.columns}
        assert "id" in columns
        assert "name" in columns
        assert "base_url" in columns
        assert "auth_config" in columns
        assert "status" in columns
        assert "tags" in columns

    def test_endpoint_row_has_expected_columns(self):
        columns = {c.name for c in ServiceEndpointRow.__table__.columns}
        assert "id" in columns
        assert "system_id" in columns
        assert "method" in columns
        assert "path" in columns
        assert "risk_level" in columns
        assert "required_permissions" in columns
        assert "when_to_use" in columns
