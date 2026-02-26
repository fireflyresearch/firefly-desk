# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Google Cloud Storage adapter."""

from __future__ import annotations

import json
import logging
from pathlib import PurePosixPath

from flydesk.knowledge.document_source import (
    IMPORTABLE_EXTENSIONS,
    DocumentSourceFactory,
    StorageContainer,
    StorageObject,
)

logger = logging.getLogger(__name__)


class GCSAdapter:
    """Adapter for Google Cloud Storage."""

    def __init__(self, config: dict) -> None:
        self._project_id = config.get("project_id", "")
        self._bucket = config.get("bucket", "")
        self._prefix = config.get("prefix", "")
        self._service_account_json = config.get("service_account_json", "")
        self._client = None

    def _get_client(self):
        if self._client is None:
            from google.cloud import storage
            from google.oauth2 import service_account

            if self._service_account_json:
                info = json.loads(self._service_account_json)
                credentials = service_account.Credentials.from_service_account_info(
                    info
                )
                self._client = storage.Client(
                    project=self._project_id, credentials=credentials
                )
            else:
                self._client = storage.Client(project=self._project_id)
        return self._client

    @staticmethod
    def _is_importable(key: str) -> bool:
        return PurePosixPath(key).suffix.lower() in IMPORTABLE_EXTENSIONS

    async def validate_credentials(self) -> bool:
        try:
            client = self._get_client()
            bucket = client.bucket(self._bucket)
            bucket.reload()
            return True
        except Exception:
            return False

    async def list_containers(self) -> list[StorageContainer]:
        try:
            client = self._get_client()
            return [
                StorageContainer(name=b.name, region=b.location or "")
                for b in client.list_buckets()
            ]
        except Exception:
            logger.exception("Failed to list GCS buckets")
            return []

    async def list_objects(
        self, container: str, prefix: str = ""
    ) -> list[StorageObject]:
        client = self._get_client()
        bucket = client.bucket(container)
        full_prefix = f"{self._prefix}/{prefix}".strip("/")
        if full_prefix:
            full_prefix += "/"

        objects: list[StorageObject] = []
        for blob in bucket.list_blobs(prefix=full_prefix):
            name = blob.name
            if not self._is_importable(name):
                continue
            objects.append(
                StorageObject(
                    key=name,
                    size=blob.size or 0,
                    last_modified=(
                        blob.updated.isoformat() if blob.updated else ""
                    ),
                    content_type=blob.content_type or "",
                )
            )
        return objects

    async def get_object_content(self, container: str, key: str) -> bytes:
        client = self._get_client()
        bucket = client.bucket(container)
        blob = bucket.blob(key)
        return blob.download_as_bytes()

    async def aclose(self) -> None:
        self._client = None


DocumentSourceFactory.register("gcs", GCSAdapter)
