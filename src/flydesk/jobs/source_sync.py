# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Source sync job handler -- detects new/changed files in cloud sources."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from flydesk.api.document_sources import _ensure_adapters_loaded
from flydesk.jobs.handlers import ProgressCallback
from flydesk.knowledge.document_source import (
    BlobStorageProvider,
    DocumentSourceFactory,
    DriveProvider,
)
from flydesk.knowledge.document_source_repository import DocumentSourceRepository

logger = logging.getLogger(__name__)


class SourceSyncHandler:
    """Syncs document sources by detecting new/changed files.

    Conforms to the :class:`~flydesk.jobs.handlers.JobHandler` protocol so it
    can be registered with the :class:`~flydesk.jobs.runner.JobRunner` under
    the ``"source_sync"`` job type.

    When executed via the job runner the *payload* must contain a
    ``"source_id"`` key.  The handler can also be called directly through
    :meth:`sync_source` for ad-hoc / cron-based sync.
    """

    def __init__(self, source_repo: DocumentSourceRepository) -> None:
        self._source_repo = source_repo

    # -- JobHandler protocol ---------------------------------------------------

    async def execute(
        self,
        job_id: str,
        payload: dict,
        on_progress: ProgressCallback,
    ) -> dict:
        """Execute sync as a background job (JobHandler protocol)."""
        source_id = payload.get("source_id", "")
        if not source_id:
            return {"error": "Missing source_id in payload"}

        await on_progress(10, f"Starting sync for source {source_id}")
        result = await self.sync_source(source_id)
        pct = 100 if "error" not in result else 0
        msg = "Sync complete" if "error" not in result else result["error"]
        await on_progress(pct, msg)
        return result

    # -- Core sync logic -------------------------------------------------------

    async def sync_source(self, source_id: str) -> dict:
        """Run sync for a single source.  Returns a summary dict."""
        config = await self._source_repo.get_decrypted_config(source_id)
        if config is None:
            return {"error": f"Source {source_id} not found"}

        row = await self._source_repo.get_row(source_id)
        if row is None:
            return {"error": f"Source {source_id} not found"}

        _ensure_adapters_loaded(row.source_type)
        adapter = DocumentSourceFactory.create(row.source_type, config)

        try:
            file_count = 0
            if isinstance(adapter, BlobStorageProvider):
                containers = await adapter.list_containers()
                for container in containers:
                    objects = await adapter.list_objects(container.name)
                    file_count += len(objects)
            elif isinstance(adapter, DriveProvider):
                drives = await adapter.list_drives()
                for drive in drives:
                    items = await adapter.list_items(drive.id)
                    file_count += len([i for i in items if not i.is_folder])

            now = datetime.now(timezone.utc)
            await self._source_repo.update_last_sync(source_id, now)

            return {
                "source_id": source_id,
                "source_type": row.source_type,
                "files_found": file_count,
                "synced_at": now.isoformat(),
            }
        except Exception as exc:
            logger.exception("Sync failed for source %s", source_id)
            return {"error": str(exc), "source_id": source_id}
        finally:
            await adapter.aclose()


async def run_sync_for_all(source_repo: DocumentSourceRepository) -> list[dict]:
    """Run sync for all enabled sources.  Called by the scheduler."""
    handler = SourceSyncHandler(source_repo)
    rows = await source_repo.list_sync_enabled()
    results: list[dict] = []
    for row in rows:
        result = await handler.sync_source(row.id)
        results.append(result)
    return results
