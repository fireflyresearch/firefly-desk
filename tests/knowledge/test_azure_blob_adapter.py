# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for Azure Blob Storage adapter."""

from __future__ import annotations

from flydesk.knowledge.adapters.azure_blob import AzureBlobAdapter
from flydesk.knowledge.document_source import DocumentSourceFactory


class TestAzureBlobAdapter:
    def test_registered_in_factory(self):
        import flydesk.knowledge.adapters.azure_blob  # noqa: F401

        assert "azure_blob" in DocumentSourceFactory.registered_types()

    def test_filters_importable_extensions(self):
        adapter = AzureBlobAdapter(
            {
                "account_name": "testaccount",
                "container": "docs",
                "connection_string": "DefaultEndpointsProtocol=https;...",
            }
        )
        assert adapter._is_importable("reports/annual.pdf") is True
        assert adapter._is_importable("archive.zip") is False
        assert adapter._is_importable("notes.txt") is True
        assert adapter._is_importable("config.yaml") is True

    def test_constructor(self):
        adapter = AzureBlobAdapter(
            {
                "account_name": "myaccount",
                "container": "my-container",
                "prefix": "data",
                "connection_string": "conn-str",
            }
        )
        assert adapter._account_name == "myaccount"
        assert adapter._container == "my-container"
        assert adapter._prefix == "data"
        assert adapter._connection_string == "conn-str"
        assert adapter._service_client is None
