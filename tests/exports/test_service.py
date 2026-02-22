# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for ExportService -- CSV, JSON, PDF generation and orchestration."""

from __future__ import annotations

import csv
import io
import json
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydek.exports.models import ExportFormat, ExportStatus, ExportTemplate
from flydek.exports.repository import ExportRepository
from flydek.exports.service import ExportService
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
def storage():
    mock = AsyncMock()
    mock.store.return_value = "/exports/test-file.csv"
    return mock


@pytest.fixture
def service(repo, storage):
    return ExportService(repo, storage)


SOURCE_TABLE = {
    "columns": ["id", "name", "email"],
    "rows": [
        ["1", "Alice", "alice@example.com"],
        ["2", "Bob", "bob@example.com"],
    ],
}

SOURCE_ITEMS = {
    "items": [
        {"id": "1", "name": "Alice", "email": "alice@example.com"},
        {"id": "2", "name": "Bob", "bob@example.com": ""},
    ],
}


class TestCSVGeneration:
    def test_generate_csv_from_table_data(self, service):
        """generate_csv produces valid CSV from columns/rows data."""
        file_bytes, row_count = service.generate_csv(SOURCE_TABLE)
        assert row_count == 2
        text = file_bytes.decode("utf-8")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        assert rows[0] == ["id", "name", "email"]
        assert rows[1] == ["1", "Alice", "alice@example.com"]
        assert rows[2] == ["2", "Bob", "bob@example.com"]

    def test_generate_csv_from_items_format(self, service):
        """generate_csv converts items list-of-dicts to CSV."""
        items_data = {
            "items": [
                {"id": "1", "name": "Alice"},
                {"id": "2", "name": "Bob"},
            ],
        }
        file_bytes, row_count = service.generate_csv(items_data)
        assert row_count == 2
        text = file_bytes.decode("utf-8")
        assert "id" in text
        assert "Alice" in text

    def test_generate_csv_with_template_mapping(self, service):
        """generate_csv applies column_mapping from template."""
        template = ExportTemplate(
            id="tpl-1",
            name="Mapped",
            format=ExportFormat.CSV,
            column_mapping={"id": "ID", "name": "Full Name"},
        )
        file_bytes, row_count = service.generate_csv(SOURCE_TABLE, template)
        assert row_count == 2
        text = file_bytes.decode("utf-8")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        # Only mapped columns should appear
        assert rows[0] == ["ID", "Full Name"]
        assert rows[1] == ["1", "Alice"]


class TestJSONGeneration:
    def test_generate_json_from_table_data(self, service):
        """generate_json produces valid JSON from columns/rows data."""
        file_bytes, row_count = service.generate_json(SOURCE_TABLE)
        assert row_count == 2
        parsed = json.loads(file_bytes.decode("utf-8"))
        assert isinstance(parsed, list)
        assert len(parsed) == 2
        assert parsed[0]["id"] == "1"
        assert parsed[0]["name"] == "Alice"
        assert parsed[1]["id"] == "2"

    def test_generate_json_with_template_mapping(self, service):
        """generate_json filters and renames keys per template mapping."""
        template = ExportTemplate(
            id="tpl-1",
            name="Mapped",
            format=ExportFormat.JSON,
            column_mapping={"id": "ID", "name": "Full Name"},
        )
        file_bytes, row_count = service.generate_json(SOURCE_TABLE, template)
        assert row_count == 2
        parsed = json.loads(file_bytes.decode("utf-8"))
        assert parsed[0] == {"ID": "1", "Full Name": "Alice"}
        # The email column should be excluded since it's not in the mapping
        assert "email" not in parsed[0]


class TestPDFGeneration:
    def test_generate_pdf_falls_back_to_html(self, service):
        """generate_pdf returns HTML fallback when weasyprint is unavailable."""
        file_bytes, row_count, actual_format = service.generate_pdf(SOURCE_TABLE)
        assert row_count == 2
        # In test env weasyprint is typically not installed
        assert actual_format in ("pdf", "html")
        if actual_format == "html":
            html = file_bytes.decode("utf-8")
            assert "<table>" in html
            assert "Alice" in html
            assert "Bob" in html


class TestExportOrchestration:
    async def test_create_export_csv_end_to_end(self, service, repo, storage):
        """create_export generates CSV, stores it, and updates the record."""
        record = await service.create_export(
            user_id="user-1",
            fmt=ExportFormat.CSV,
            source_data=SOURCE_TABLE,
            title="My CSV Export",
        )
        assert record.status == ExportStatus.COMPLETED
        assert record.row_count == 2
        assert record.file_size is not None
        assert record.file_size > 0
        assert record.completed_at is not None

        # Storage should have been called
        storage.store.assert_called_once()

        # Record should be persisted in DB
        persisted = await repo.get_export(record.id)
        assert persisted is not None
        assert persisted.status == ExportStatus.COMPLETED

    async def test_create_export_with_template(self, service, repo, storage):
        """create_export resolves a template and applies it during generation."""
        # First create a template in the DB
        template = ExportTemplate(
            id="tpl-csv",
            name="CSV Template",
            format=ExportFormat.CSV,
            column_mapping={"id": "ID", "name": "Full Name"},
        )
        await repo.create_template(template)

        record = await service.create_export(
            user_id="user-1",
            fmt=ExportFormat.CSV,
            source_data=SOURCE_TABLE,
            title="Templated Export",
            template_id="tpl-csv",
        )
        assert record.status == ExportStatus.COMPLETED
        assert record.template_id == "tpl-csv"

        # Verify the stored file content uses mapped columns
        stored_bytes = storage.store.call_args[0][1]
        text = stored_bytes.decode("utf-8")
        assert "ID" in text
        assert "Full Name" in text

    async def test_create_export_failure_updates_status(self, service, repo, storage):
        """When generation fails the record status becomes FAILED."""
        storage.store.side_effect = RuntimeError("Disk full")

        record = await service.create_export(
            user_id="user-1",
            fmt=ExportFormat.CSV,
            source_data=SOURCE_TABLE,
            title="Failing Export",
        )
        assert record.status == ExportStatus.FAILED
        assert record.error == "Export generation failed"
        assert record.completed_at is not None
