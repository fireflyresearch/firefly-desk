# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Azure Blob Storage adapter."""

from __future__ import annotations

import logging
from pathlib import PurePosixPath

from flydesk.knowledge.document_source import (
    IMPORTABLE_EXTENSIONS,
    DocumentSourceFactory,
    StorageContainer,
    StorageObject,
)

logger = logging.getLogger(__name__)


class AzureBlobAdapter:
    """Adapter for Azure Blob Storage."""

    def __init__(self, config: dict) -> None:
        self._account_name = config.get("account_name", "")
        self._container = config.get("container", "")
        self._prefix = config.get("prefix", "")
        self._connection_string = config.get("connection_string", "")
        self._service_client = None

    def _get_service_client(self):
        if self._service_client is None:
            from azure.storage.blob import BlobServiceClient

            if self._connection_string:
                self._service_client = BlobServiceClient.from_connection_string(
                    self._connection_string
                )
            else:
                account_url = f"https://{self._account_name}.blob.core.windows.net"
                self._service_client = BlobServiceClient(account_url=account_url)
        return self._service_client

    @staticmethod
    def _is_importable(key: str) -> bool:
        return PurePosixPath(key).suffix.lower() in IMPORTABLE_EXTENSIONS

    async def validate_credentials(self) -> bool:
        try:
            client = self._get_service_client()
            container_client = client.get_container_client(self._container)
            container_client.get_container_properties()
            return True
        except Exception:
            return False

    async def list_containers(self) -> list[StorageContainer]:
        try:
            client = self._get_service_client()
            return [
                StorageContainer(name=c["name"])
                for c in client.list_containers()
            ]
        except Exception:
            logger.exception("Failed to list Azure Blob containers")
            return []

    async def list_objects(
        self, container: str, prefix: str = ""
    ) -> list[StorageObject]:
        client = self._get_service_client()
        container_client = client.get_container_client(container)
        full_prefix = f"{self._prefix}/{prefix}".strip("/")
        if full_prefix:
            full_prefix += "/"

        objects: list[StorageObject] = []
        for blob in container_client.list_blobs(name_starts_with=full_prefix):
            name = blob["name"]
            if not self._is_importable(name):
                continue
            objects.append(
                StorageObject(
                    key=name,
                    size=blob.get("size", 0),
                    last_modified=(
                        blob["last_modified"].isoformat()
                        if blob.get("last_modified")
                        else ""
                    ),
                    content_type=blob.get("content_type", ""),
                )
            )
        return objects

    async def get_object_content(self, container: str, key: str) -> bytes:
        client = self._get_service_client()
        blob_client = client.get_blob_client(container=container, blob=key)
        return blob_client.download_blob().readall()

    async def aclose(self) -> None:
        self._service_client = None


DocumentSourceFactory.register("azure_blob", AzureBlobAdapter)
