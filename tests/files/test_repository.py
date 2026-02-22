# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for FileUploadRepository."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydek.files.models import FileUpload
from flydek.files.repository import FileUploadRepository
from flydek.models.base import Base


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def repo(session_factory):
    return FileUploadRepository(session_factory)


@pytest.fixture
def sample_upload() -> FileUpload:
    return FileUpload(
        id="file-1",
        conversation_id="conv-1",
        user_id="user-1",
        filename="test.txt",
        content_type="text/plain",
        file_size=13,
        storage_path="/tmp/uploads/abc.txt",
        storage_backend="local",
        extracted_text="Hello, world!",
    )


class TestFileUploadRepository:
    async def test_create_and_get_file(self, repo, sample_upload):
        """Creating a file upload and retrieving it returns the same data."""
        await repo.create(sample_upload)
        result = await repo.get("file-1")
        assert result is not None
        assert result.id == "file-1"
        assert result.filename == "test.txt"
        assert result.content_type == "text/plain"
        assert result.file_size == 13
        assert result.user_id == "user-1"
        assert result.conversation_id == "conv-1"
        assert result.extracted_text == "Hello, world!"

    async def test_list_by_conversation(self, repo, sample_upload):
        """Listing by conversation returns only files for that conversation."""
        await repo.create(sample_upload)

        upload2 = FileUpload(
            id="file-2",
            conversation_id="conv-1",
            user_id="user-1",
            filename="image.png",
            content_type="image/png",
            file_size=1024,
            storage_path="/tmp/uploads/img.png",
        )
        await repo.create(upload2)

        upload3 = FileUpload(
            id="file-3",
            conversation_id="conv-2",
            user_id="user-1",
            filename="other.txt",
            content_type="text/plain",
            file_size=5,
            storage_path="/tmp/uploads/other.txt",
        )
        await repo.create(upload3)

        results = await repo.list_by_conversation("conv-1")
        assert len(results) == 2
        ids = {r.id for r in results}
        assert ids == {"file-1", "file-2"}

    async def test_delete_file(self, repo, sample_upload):
        """Deleting a file removes it from the database."""
        await repo.create(sample_upload)
        await repo.delete("file-1")
        result = await repo.get("file-1")
        assert result is None

    async def test_get_nonexistent_returns_none(self, repo):
        """Getting a non-existent file returns None."""
        result = await repo.get("nonexistent")
        assert result is None

    async def test_list_empty_conversation(self, repo):
        """Listing by a conversation with no files returns an empty list."""
        results = await repo.list_by_conversation("empty-conv")
        assert results == []

    async def test_file_without_conversation(self, repo):
        """A file upload without a conversation_id can be created and retrieved."""
        upload = FileUpload(
            id="file-orphan",
            user_id="user-1",
            filename="standalone.pdf",
            content_type="application/pdf",
            file_size=4096,
            storage_path="/tmp/uploads/standalone.pdf",
        )
        await repo.create(upload)
        result = await repo.get("file-orphan")
        assert result is not None
        assert result.conversation_id is None
