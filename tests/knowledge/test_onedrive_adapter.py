# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for OneDrive adapter."""

from __future__ import annotations

from flydesk.knowledge.adapters.onedrive import OneDriveAdapter
from flydesk.knowledge.document_source import DocumentSourceFactory


class TestOneDriveAdapter:
    def test_registered_in_factory(self):
        import flydesk.knowledge.adapters.onedrive  # noqa: F401

        assert "onedrive" in DocumentSourceFactory.registered_types()

    def test_filters_importable_extensions(self):
        adapter = OneDriveAdapter(
            {
                "tenant_id": "tid",
                "client_id": "cid",
                "client_secret": "secret",
                "drive_id": "did",
            }
        )
        assert adapter._is_importable("document.docx") is True
        assert adapter._is_importable("photo.jpg") is False
        assert adapter._is_importable("notes.txt") is True
        assert adapter._is_importable("config.yml") is True

    def test_constructor(self):
        adapter = OneDriveAdapter(
            {
                "tenant_id": "my-tenant",
                "client_id": "my-client",
                "client_secret": "my-secret",
                "drive_id": "my-drive",
                "folder_path": "/Documents",
            }
        )
        assert adapter._tenant_id == "my-tenant"
        assert adapter._client_id == "my-client"
        assert adapter._drive_id == "my-drive"
        assert adapter._folder_path == "/Documents"
        assert adapter._http_client is None
        assert adapter._msal_app is None
