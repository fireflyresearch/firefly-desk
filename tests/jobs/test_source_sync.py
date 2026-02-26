# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for SourceSyncHandler -- cloud source sync job."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from flydesk.jobs.handlers import JobHandler
from flydesk.jobs.source_sync import SourceSyncHandler, run_sync_for_all
from flydesk.knowledge.document_source import (
    DriveInfo,
    DriveItem,
    StorageContainer,
    StorageObject,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_row(
    source_id: str = "src-1",
    source_type: str = "s3",
    sync_enabled: bool = True,
) -> SimpleNamespace:
    """Create a minimal row-like object returned by the repository."""
    return SimpleNamespace(
        id=source_id,
        source_type=source_type,
        sync_enabled=sync_enabled,
        is_active=True,
    )


def _blob_adapter(containers: list[StorageContainer], objects_map: dict[str, list[StorageObject]]):
    """Build an AsyncMock that satisfies BlobStorageProvider protocol."""
    from flydesk.knowledge.document_source import BlobStorageProvider

    adapter = AsyncMock(spec=BlobStorageProvider)
    adapter.list_containers = AsyncMock(return_value=containers)
    adapter.list_objects = AsyncMock(side_effect=lambda c, prefix="": objects_map.get(c, []))
    adapter.get_object_content = AsyncMock(return_value=b"data")
    adapter.validate_credentials = AsyncMock(return_value=True)
    adapter.aclose = AsyncMock()
    return adapter


def _drive_adapter(drives: list[DriveInfo], items_map: dict[str, list[DriveItem]]):
    """Build an AsyncMock that satisfies DriveProvider protocol."""
    from flydesk.knowledge.document_source import DriveProvider

    adapter = AsyncMock(spec=DriveProvider)
    adapter.list_drives = AsyncMock(return_value=drives)
    adapter.list_items = AsyncMock(side_effect=lambda d, folder_id="": items_map.get(d, []))
    adapter.get_file_content = AsyncMock(return_value=b"data")
    adapter.validate_credentials = AsyncMock(return_value=True)
    adapter.aclose = AsyncMock()
    return adapter


def _mock_repo(
    config: dict | None = None,
    row: SimpleNamespace | None = None,
    sync_enabled_rows: list | None = None,
) -> AsyncMock:
    """Build an AsyncMock DocumentSourceRepository."""
    repo = AsyncMock()
    repo.get_decrypted_config = AsyncMock(return_value=config)
    repo.get_row = AsyncMock(return_value=row)
    repo.update_last_sync = AsyncMock()
    repo.list_sync_enabled = AsyncMock(return_value=sync_enabled_rows or [])
    return repo


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSourceSyncHandler:
    """Tests for SourceSyncHandler."""

    async def test_conforms_to_job_handler_protocol(self):
        """SourceSyncHandler satisfies the JobHandler protocol."""
        handler = SourceSyncHandler(AsyncMock())
        assert isinstance(handler, JobHandler)

    @patch("flydesk.jobs.source_sync._ensure_adapters_loaded")
    @patch("flydesk.jobs.source_sync.DocumentSourceFactory")
    async def test_sync_handler_blob(self, mock_factory, mock_ensure):
        """Blob adapter: containers and objects are counted correctly."""
        containers = [StorageContainer(name="bucket-a"), StorageContainer(name="bucket-b")]
        objects_map = {
            "bucket-a": [
                StorageObject(key="file1.txt", size=100, last_modified="2026-01-01"),
                StorageObject(key="file2.pdf", size=200, last_modified="2026-01-02"),
            ],
            "bucket-b": [
                StorageObject(key="file3.md", size=50, last_modified="2026-01-03"),
            ],
        }
        adapter = _blob_adapter(containers, objects_map)
        mock_factory.create.return_value = adapter

        row = _make_row(source_type="s3")
        repo = _mock_repo(config={"bucket": "bucket-a"}, row=row)

        handler = SourceSyncHandler(repo)
        result = await handler.sync_source("src-1")

        assert result["source_id"] == "src-1"
        assert result["source_type"] == "s3"
        assert result["files_found"] == 3
        assert "synced_at" in result
        assert "error" not in result

        adapter.aclose.assert_awaited_once()

    @patch("flydesk.jobs.source_sync._ensure_adapters_loaded")
    @patch("flydesk.jobs.source_sync.DocumentSourceFactory")
    async def test_sync_handler_drive(self, mock_factory, mock_ensure):
        """Drive adapter: only non-folder items are counted."""
        drives = [DriveInfo(id="drive-1", name="My Drive")]
        items_map = {
            "drive-1": [
                DriveItem(id="f1", name="doc.txt", path="/doc.txt", is_folder=False, size=100),
                DriveItem(id="f2", name="Photos", path="/Photos", is_folder=True),
                DriveItem(id="f3", name="report.pdf", path="/report.pdf", is_folder=False, size=500),
            ],
        }
        adapter = _drive_adapter(drives, items_map)
        mock_factory.create.return_value = adapter

        row = _make_row(source_type="onedrive")
        repo = _mock_repo(config={"tenant_id": "t1"}, row=row)

        handler = SourceSyncHandler(repo)
        result = await handler.sync_source("src-1")

        assert result["files_found"] == 2
        assert result["source_type"] == "onedrive"
        assert "error" not in result

        adapter.aclose.assert_awaited_once()

    async def test_sync_handler_source_not_found_config(self):
        """Returns error dict when decrypted config is None."""
        repo = _mock_repo(config=None, row=None)
        handler = SourceSyncHandler(repo)
        result = await handler.sync_source("missing-id")

        assert "error" in result
        assert "missing-id" in result["error"]

    async def test_sync_handler_source_not_found_row(self):
        """Returns error dict when row is None (config exists but row gone)."""
        repo = _mock_repo(config={"bucket": "x"}, row=None)
        handler = SourceSyncHandler(repo)
        result = await handler.sync_source("ghost-id")

        assert "error" in result
        assert "ghost-id" in result["error"]

    @patch("flydesk.jobs.source_sync._ensure_adapters_loaded")
    @patch("flydesk.jobs.source_sync.DocumentSourceFactory")
    async def test_sync_updates_last_sync(self, mock_factory, mock_ensure):
        """update_last_sync is called with a UTC timestamp on success."""
        adapter = _blob_adapter([], {})
        mock_factory.create.return_value = adapter

        row = _make_row(source_type="gcs")
        repo = _mock_repo(config={"project_id": "p1"}, row=row)

        handler = SourceSyncHandler(repo)
        await handler.sync_source("src-1")

        repo.update_last_sync.assert_awaited_once()
        call_args = repo.update_last_sync.call_args
        assert call_args[0][0] == "src-1"
        ts = call_args[0][1]
        assert isinstance(ts, datetime)
        assert ts.tzinfo == timezone.utc

    @patch("flydesk.jobs.source_sync._ensure_adapters_loaded")
    @patch("flydesk.jobs.source_sync.DocumentSourceFactory")
    async def test_sync_adapter_error_returns_error_dict(self, mock_factory, mock_ensure):
        """When the adapter raises, the error is captured in the result."""
        adapter = _blob_adapter([], {})
        # Override list_containers to raise after creation
        adapter.list_containers = AsyncMock(side_effect=ConnectionError("timeout"))
        mock_factory.create.return_value = adapter

        row = _make_row(source_type="s3")
        repo = _mock_repo(config={"bucket": "b"}, row=row)

        handler = SourceSyncHandler(repo)
        result = await handler.sync_source("src-1")

        assert "error" in result
        assert result["source_id"] == "src-1"
        # aclose is still called in the finally block
        adapter.aclose.assert_awaited_once()

    @patch("flydesk.jobs.source_sync._ensure_adapters_loaded")
    @patch("flydesk.jobs.source_sync.DocumentSourceFactory")
    async def test_execute_via_job_handler_protocol(self, mock_factory, mock_ensure):
        """execute() with job_id/payload/on_progress works as JobHandler."""
        adapter = _blob_adapter(
            [StorageContainer(name="b1")],
            {"b1": [StorageObject(key="a.txt", size=10, last_modified="2026-01-01")]},
        )
        mock_factory.create.return_value = adapter

        row = _make_row()
        repo = _mock_repo(config={"bucket": "b1"}, row=row)

        handler = SourceSyncHandler(repo)
        on_progress = AsyncMock()

        result = await handler.execute("job-123", {"source_id": "src-1"}, on_progress)

        assert result["files_found"] == 1
        # Progress was reported at start (10%) and completion (100%)
        assert on_progress.await_count == 2
        first_call = on_progress.call_args_list[0]
        assert first_call[0][0] == 10
        last_call = on_progress.call_args_list[1]
        assert last_call[0][0] == 100

    async def test_execute_missing_source_id_in_payload(self):
        """execute() with empty payload returns error."""
        handler = SourceSyncHandler(AsyncMock())
        on_progress = AsyncMock()
        result = await handler.execute("job-1", {}, on_progress)

        assert "error" in result
        assert "Missing source_id" in result["error"]


class TestRunSyncForAll:
    """Tests for run_sync_for_all convenience function."""

    @patch("flydesk.jobs.source_sync._ensure_adapters_loaded")
    @patch("flydesk.jobs.source_sync.DocumentSourceFactory")
    async def test_run_sync_for_all_multiple_sources(self, mock_factory, mock_ensure):
        """All sync-enabled sources are synced."""
        row1 = _make_row(source_id="src-1", source_type="s3")
        row2 = _make_row(source_id="src-2", source_type="onedrive")

        adapter1 = _blob_adapter(
            [StorageContainer(name="b")],
            {"b": [StorageObject(key="f.txt", size=1, last_modified="2026-01-01")]},
        )
        adapter2 = _drive_adapter(
            [DriveInfo(id="d1", name="Drive")],
            {"d1": [DriveItem(id="i1", name="x.pdf", path="/x.pdf", is_folder=False)]},
        )

        # Factory returns different adapters per call
        mock_factory.create.side_effect = [adapter1, adapter2]

        repo = AsyncMock()
        repo.list_sync_enabled = AsyncMock(return_value=[row1, row2])
        repo.get_decrypted_config = AsyncMock(side_effect=[{"bucket": "b"}, {"tenant_id": "t"}])
        repo.get_row = AsyncMock(side_effect=[row1, row2])
        repo.update_last_sync = AsyncMock()

        results = await run_sync_for_all(repo)

        assert len(results) == 2
        assert results[0]["source_id"] == "src-1"
        assert results[0]["files_found"] == 1
        assert results[1]["source_id"] == "src-2"
        assert results[1]["files_found"] == 1

    async def test_run_sync_for_all_no_enabled_sources(self):
        """Returns empty list when no sources are sync-enabled."""
        repo = _mock_repo(sync_enabled_rows=[])
        results = await run_sync_for_all(repo)
        assert results == []
