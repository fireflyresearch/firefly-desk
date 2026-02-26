# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for S3 adapter."""

from __future__ import annotations

from flydesk.knowledge.adapters.s3 import S3Adapter
from flydesk.knowledge.document_source import DocumentSourceFactory


class TestS3Adapter:
    def test_registered_in_factory(self):
        import flydesk.knowledge.adapters.s3  # noqa: F401

        assert "s3" in DocumentSourceFactory.registered_types()

    def test_filters_importable_extensions(self):
        adapter = S3Adapter(
            {
                "bucket": "test",
                "region": "us-east-1",
                "access_key_id": "AK",
                "secret_access_key": "SK",
            }
        )
        assert adapter._is_importable("docs/readme.md") is True
        assert adapter._is_importable("binary.exe") is False
        assert adapter._is_importable("data.pdf") is True

    def test_constructor(self):
        adapter = S3Adapter(
            {
                "bucket": "my-bucket",
                "region": "eu-west-1",
                "prefix": "uploads",
                "access_key_id": "AKID",
                "secret_access_key": "SECRET",
                "endpoint_url": "https://s3.custom.com",
            }
        )
        assert adapter._bucket == "my-bucket"
        assert adapter._region == "eu-west-1"
        assert adapter._prefix == "uploads"
        assert adapter._endpoint_url == "https://s3.custom.com"
        assert adapter._client is None
