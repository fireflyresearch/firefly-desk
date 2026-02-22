# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for ExportRepository -- CRUD for exports and templates."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydek.exports.models import ExportFormat, ExportRecord, ExportStatus, ExportTemplate
from flydek.exports.repository import ExportRepository
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
def repo(session_factory):
    return ExportRepository(session_factory)


@pytest.fixture
def sample_export() -> ExportRecord:
    return ExportRecord(
        id="exp-1",
        user_id="user-1",
        format=ExportFormat.CSV,
        title="Test Export",
        description="A test CSV export",
        status=ExportStatus.PENDING,
        source_data={"columns": ["id", "name"], "rows": [["1", "Alice"]]},
    )


@pytest.fixture
def sample_template() -> ExportTemplate:
    return ExportTemplate(
        id="tpl-1",
        name="Standard CSV",
        format=ExportFormat.CSV,
        column_mapping={"id": "ID", "name": "Full Name"},
        header_text="My Report",
        footer_text="End of report",
    )


class TestExportRepository:
    async def test_create_and_get_export(self, repo, sample_export):
        """Creating an export and retrieving it returns matching data."""
        await repo.create_export(sample_export)
        result = await repo.get_export("exp-1")
        assert result is not None
        assert result.id == "exp-1"
        assert result.user_id == "user-1"
        assert result.format == ExportFormat.CSV
        assert result.title == "Test Export"
        assert result.status == ExportStatus.PENDING
        assert result.source_data == {"columns": ["id", "name"], "rows": [["1", "Alice"]]}

    async def test_get_nonexistent_export_returns_none(self, repo):
        """Getting a non-existent export returns None."""
        result = await repo.get_export("nonexistent")
        assert result is None

    async def test_list_exports_by_user(self, repo, sample_export):
        """list_exports returns only exports for the given user."""
        await repo.create_export(sample_export)

        export2 = ExportRecord(
            id="exp-2",
            user_id="user-1",
            format=ExportFormat.JSON,
            title="Second Export",
        )
        await repo.create_export(export2)

        # Different user
        export3 = ExportRecord(
            id="exp-3",
            user_id="user-2",
            format=ExportFormat.PDF,
            title="Other User Export",
        )
        await repo.create_export(export3)

        results = await repo.list_exports("user-1")
        assert len(results) == 2
        ids = {r.id for r in results}
        assert ids == {"exp-1", "exp-2"}

    async def test_update_export(self, repo, sample_export):
        """Updating an export persists the new field values."""
        await repo.create_export(sample_export)

        sample_export.status = ExportStatus.COMPLETED
        sample_export.file_path = "/exports/exp-1.csv"
        sample_export.file_size = 42
        sample_export.row_count = 1
        await repo.update_export(sample_export)

        result = await repo.get_export("exp-1")
        assert result is not None
        assert result.status == ExportStatus.COMPLETED
        assert result.file_path == "/exports/exp-1.csv"
        assert result.file_size == 42
        assert result.row_count == 1

    async def test_delete_export(self, repo, sample_export):
        """Deleting an export removes it from the database."""
        await repo.create_export(sample_export)
        await repo.delete_export("exp-1")
        result = await repo.get_export("exp-1")
        assert result is None

    async def test_create_and_get_template(self, repo, sample_template):
        """Creating a template and retrieving it returns matching data."""
        await repo.create_template(sample_template)
        result = await repo.get_template("tpl-1")
        assert result is not None
        assert result.id == "tpl-1"
        assert result.name == "Standard CSV"
        assert result.format == ExportFormat.CSV
        assert result.column_mapping == {"id": "ID", "name": "Full Name"}
        assert result.header_text == "My Report"
        assert result.footer_text == "End of report"

    async def test_list_templates(self, repo, sample_template):
        """list_templates returns all templates ordered by name."""
        await repo.create_template(sample_template)

        tpl2 = ExportTemplate(
            id="tpl-2",
            name="Another Template",
            format=ExportFormat.JSON,
        )
        await repo.create_template(tpl2)

        results = await repo.list_templates()
        assert len(results) == 2
        # Ordered by name ascending
        assert results[0].name == "Another Template"
        assert results[1].name == "Standard CSV"

    async def test_delete_template(self, repo, sample_template):
        """Deleting a template removes it from the database."""
        await repo.create_template(sample_template)
        await repo.delete_template("tpl-1")
        result = await repo.get_template("tpl-1")
        assert result is None
