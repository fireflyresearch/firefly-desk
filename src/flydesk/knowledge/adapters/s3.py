# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""S3-compatible blob storage adapter."""

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


class S3Adapter:
    """Adapter for AWS S3 (and S3-compatible) blob storage."""

    def __init__(self, config: dict) -> None:
        self._bucket = config.get("bucket", "")
        self._region = config.get("region", "us-east-1")
        self._prefix = config.get("prefix", "")
        self._access_key_id = config.get("access_key_id", "")
        self._secret_access_key = config.get("secret_access_key", "")
        self._endpoint_url = config.get("endpoint_url")
        self._client = None

    def _get_client(self):
        if self._client is None:
            import boto3

            kwargs = {
                "service_name": "s3",
                "region_name": self._region,
                "aws_access_key_id": self._access_key_id,
                "aws_secret_access_key": self._secret_access_key,
            }
            if self._endpoint_url:
                kwargs["endpoint_url"] = self._endpoint_url
            self._client = boto3.client(**kwargs)
        return self._client

    @staticmethod
    def _is_importable(key: str) -> bool:
        return PurePosixPath(key).suffix.lower() in IMPORTABLE_EXTENSIONS

    async def validate_credentials(self) -> bool:
        try:
            client = self._get_client()
            client.head_bucket(Bucket=self._bucket)
            return True
        except Exception:
            return False

    async def list_containers(self) -> list[StorageContainer]:
        try:
            client = self._get_client()
            response = client.list_buckets()
            return [
                StorageContainer(name=b["Name"], region=self._region)
                for b in response.get("Buckets", [])
            ]
        except Exception:
            logger.exception("Failed to list S3 buckets")
            return []

    async def list_objects(
        self, container: str, prefix: str = ""
    ) -> list[StorageObject]:
        client = self._get_client()
        full_prefix = f"{self._prefix}/{prefix}".strip("/")
        if full_prefix:
            full_prefix += "/"

        objects: list[StorageObject] = []
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=container, Prefix=full_prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if not self._is_importable(key):
                    continue
                objects.append(
                    StorageObject(
                        key=key,
                        size=obj.get("Size", 0),
                        last_modified=(
                            obj["LastModified"].isoformat()
                            if obj.get("LastModified")
                            else ""
                        ),
                        content_type=obj.get("ContentType", ""),
                    )
                )
        return objects

    async def get_object_content(self, container: str, key: str) -> bytes:
        client = self._get_client()
        response = client.get_object(Bucket=container, Key=key)
        return response["Body"].read()

    async def aclose(self) -> None:
        self._client = None


DocumentSourceFactory.register("s3", S3Adapter)
