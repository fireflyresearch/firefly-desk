# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for Google Cloud Storage adapter."""

from __future__ import annotations

from flydesk.knowledge.adapters.gcs import GCSAdapter
from flydesk.knowledge.document_source import DocumentSourceFactory


class TestGCSAdapter:
    def test_registered_in_factory(self):
        import flydesk.knowledge.adapters.gcs  # noqa: F401

        assert "gcs" in DocumentSourceFactory.registered_types()

    def test_filters_importable_extensions(self):
        adapter = GCSAdapter(
            {
                "project_id": "my-project",
                "bucket": "my-bucket",
            }
        )
        assert adapter._is_importable("folder/report.pdf") is True
        assert adapter._is_importable("image.png") is False
        assert adapter._is_importable("data.json") is True
        assert adapter._is_importable("readme.md") is True

    def test_constructor(self):
        adapter = GCSAdapter(
            {
                "project_id": "test-project",
                "bucket": "test-bucket",
                "prefix": "documents",
                "service_account_json": '{"type":"service_account"}',
            }
        )
        assert adapter._project_id == "test-project"
        assert adapter._bucket == "test-bucket"
        assert adapter._prefix == "documents"
        assert adapter._service_account_json == '{"type":"service_account"}'
        assert adapter._client is None
