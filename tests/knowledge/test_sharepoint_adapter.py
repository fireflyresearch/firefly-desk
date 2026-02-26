# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for SharePoint adapter."""

from __future__ import annotations

from flydesk.knowledge.adapters.sharepoint import SharePointAdapter
from flydesk.knowledge.document_source import DocumentSourceFactory


class TestSharePointAdapter:
    def test_registered_in_factory(self):
        import flydesk.knowledge.adapters.sharepoint  # noqa: F401

        assert "sharepoint" in DocumentSourceFactory.registered_types()

    def test_filters_importable_extensions(self):
        adapter = SharePointAdapter(
            {
                "tenant_id": "tid",
                "client_id": "cid",
                "client_secret": "secret",
                "site_url": "https://contoso.sharepoint.com/sites/team",
                "library_name": "Documents",
            }
        )
        assert adapter._is_importable("report.docx") is True
        assert adapter._is_importable("image.bmp") is False
        assert adapter._is_importable("data.json") is True
        assert adapter._is_importable("notes.md") is True

    def test_constructor(self):
        adapter = SharePointAdapter(
            {
                "tenant_id": "my-tenant",
                "client_id": "my-client",
                "client_secret": "my-secret",
                "site_url": "https://contoso.sharepoint.com/sites/engineering",
                "library_name": "Shared Documents",
            }
        )
        assert adapter._tenant_id == "my-tenant"
        assert adapter._client_id == "my-client"
        assert adapter._site_url == "https://contoso.sharepoint.com/sites/engineering"
        assert adapter._library_name == "Shared Documents"
        assert adapter._http_client is None
        assert adapter._site_id is None
