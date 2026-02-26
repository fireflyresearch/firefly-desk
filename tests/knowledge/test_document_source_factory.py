# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for DocumentSourceFactory and provider protocols."""

from __future__ import annotations

import pytest

from flydesk.knowledge.document_source import (
    IMPORTABLE_EXTENSIONS,
    DocumentSourceFactory,
    DriveInfo,
    DriveItem,
    StorageContainer,
    StorageObject,
)


class TestDocumentSourceFactory:
    def test_register_and_create(self):
        class FakeAdapter:
            def __init__(self, config):
                self.config = config

        DocumentSourceFactory.register("fake_blob", FakeAdapter)
        adapter = DocumentSourceFactory.create("fake_blob", {"key": "val"})
        assert isinstance(adapter, FakeAdapter)
        assert adapter.config == {"key": "val"}
        # Cleanup
        DocumentSourceFactory._registry.pop("fake_blob", None)

    def test_create_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown source type"):
            DocumentSourceFactory.create("nonexistent", {})

    def test_importable_extensions(self):
        assert ".md" in IMPORTABLE_EXTENSIONS
        assert ".pdf" in IMPORTABLE_EXTENSIONS
        assert ".docx" in IMPORTABLE_EXTENSIONS
        assert ".txt" in IMPORTABLE_EXTENSIONS
        assert ".exe" not in IMPORTABLE_EXTENSIONS


class TestDataClasses:
    def test_storage_container(self):
        c = StorageContainer(name="my-bucket", region="us-east-1")
        assert c.name == "my-bucket"

    def test_storage_object(self):
        o = StorageObject(key="docs/readme.md", size=1024, last_modified="2026-01-01T00:00:00Z", content_type="text/markdown")
        assert o.key == "docs/readme.md"

    def test_drive_info(self):
        d = DriveInfo(id="drive-1", name="My Drive", type="personal")
        assert d.id == "drive-1"

    def test_drive_item(self):
        i = DriveItem(id="item-1", name="doc.md", path="/docs/doc.md", is_folder=False, size=512, modified_at="2026-01-01", mime_type="text/markdown")
        assert not i.is_folder
