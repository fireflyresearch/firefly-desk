# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for LocalFileStorage."""

from __future__ import annotations

import os

import pytest

from flydek.files.storage import LocalFileStorage


@pytest.fixture
def storage(tmp_path):
    return LocalFileStorage(base_dir=str(tmp_path / "uploads"))


class TestLocalFileStorage:
    async def test_store_and_retrieve(self, storage):
        """Stored file content can be retrieved."""
        content = b"Hello, world!"
        path = await storage.store("test.txt", content, "text/plain")
        assert os.path.exists(path)

        retrieved = await storage.retrieve(path)
        assert retrieved == content

    async def test_delete(self, storage):
        """Deleting a stored file removes it from disk."""
        content = b"delete me"
        path = await storage.store("delete.txt", content, "text/plain")
        assert os.path.exists(path)

        await storage.delete(path)
        assert not os.path.exists(path)

    async def test_delete_nonexistent_is_noop(self, storage):
        """Deleting a non-existent path does not raise."""
        await storage.delete("/nonexistent/path.txt")

    async def test_creates_directory(self, tmp_path):
        """Storage creates the base directory if it does not exist."""
        base = str(tmp_path / "new" / "nested" / "dir")
        assert not os.path.exists(base)

        storage = LocalFileStorage(base_dir=base)
        assert os.path.isdir(base)

        # Verify we can still store
        path = await storage.store("file.txt", b"data", "text/plain")
        assert os.path.exists(path)

    async def test_store_preserves_extension(self, storage):
        """Stored files retain the original file extension."""
        path = await storage.store("report.pdf", b"%PDF", "application/pdf")
        assert path.endswith(".pdf")

    async def test_store_unique_names(self, storage):
        """Storing two files with the same name produces different paths."""
        path1 = await storage.store("doc.txt", b"first", "text/plain")
        path2 = await storage.store("doc.txt", b"second", "text/plain")
        assert path1 != path2
