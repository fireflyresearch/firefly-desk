# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for Google Drive adapter."""

from __future__ import annotations

from flydesk.knowledge.adapters.google_drive import GoogleDriveAdapter
from flydesk.knowledge.document_source import DocumentSourceFactory


class TestGoogleDriveAdapter:
    def test_registered_in_factory(self):
        import flydesk.knowledge.adapters.google_drive  # noqa: F401

        assert "google_drive" in DocumentSourceFactory.registered_types()

    def test_filters_importable_extensions(self):
        adapter = GoogleDriveAdapter(
            {
                "folder_id": "root",
                "service_account_json": '{"type":"service_account"}',
            }
        )
        assert adapter._is_importable("presentation.pdf") is True
        assert adapter._is_importable("video.mp4") is False
        assert adapter._is_importable("spec.yaml") is True
        assert adapter._is_importable("readme.md") is True

    def test_constructor(self):
        adapter = GoogleDriveAdapter(
            {
                "folder_id": "abc123",
                "service_account_json": '{"type":"service_account"}',
            }
        )
        assert adapter._folder_id == "abc123"
        assert adapter._service_account_json == '{"type":"service_account"}'
        assert adapter._service is None
