# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for multimodal file context building in DeskAgent."""

from __future__ import annotations

from unittest.mock import AsyncMock

from flydesk.agent.desk_agent import _IMAGE_CONTENT_TYPES, _build_multimodal_parts
from flydesk.files.models import FileUpload


def _make_upload(
    *,
    file_id: str = "f1",
    filename: str = "file.bin",
    content_type: str = "application/octet-stream",
    extracted_text: str | None = None,
    storage_path: str = "/tmp/file.bin",
) -> FileUpload:
    """Helper to create a FileUpload with sensible defaults."""
    return FileUpload(
        id=file_id,
        user_id="u1",
        filename=filename,
        content_type=content_type,
        file_size=100,
        storage_path=storage_path,
        extracted_text=extracted_text,
    )


class TestBuildMultimodalParts:
    """Tests for the module-level _build_multimodal_parts helper."""

    async def test_image_returns_binary_content(self):
        upload = _make_upload(
            file_id="f1",
            filename="photo.png",
            content_type="image/png",
            storage_path="/tmp/photo.png",
        )
        storage = AsyncMock()
        storage.retrieve = AsyncMock(return_value=b"\x89PNG\r\n...")

        parts = await _build_multimodal_parts([upload], storage)

        assert len(parts) == 1
        from fireflyframework_genai.types import BinaryContent

        assert isinstance(parts[0], BinaryContent)
        assert parts[0].data == b"\x89PNG\r\n..."
        assert parts[0].media_type == "image/png"
        storage.retrieve.assert_awaited_once_with("/tmp/photo.png")

    async def test_jpeg_image_returns_binary_content(self):
        upload = _make_upload(
            file_id="f1",
            filename="photo.jpg",
            content_type="image/jpeg",
            storage_path="/tmp/photo.jpg",
        )
        storage = AsyncMock()
        storage.retrieve = AsyncMock(return_value=b"\xff\xd8\xff\xe0...")

        parts = await _build_multimodal_parts([upload], storage)

        assert len(parts) == 1
        from fireflyframework_genai.types import BinaryContent

        assert isinstance(parts[0], BinaryContent)
        assert parts[0].media_type == "image/jpeg"

    async def test_text_file_returns_string(self):
        upload = _make_upload(
            file_id="f2",
            filename="notes.txt",
            content_type="text/plain",
            extracted_text="Hello world",
            storage_path="/tmp/notes.txt",
        )
        storage = AsyncMock()

        parts = await _build_multimodal_parts([upload], storage)

        assert len(parts) == 1
        assert isinstance(parts[0], str)
        assert "Hello world" in parts[0]
        assert "notes.txt" in parts[0]

    async def test_docx_returns_extracted_text(self):
        upload = _make_upload(
            file_id="f3",
            filename="doc.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            extracted_text="Document content here",
            storage_path="/tmp/doc.docx",
        )
        storage = AsyncMock()

        parts = await _build_multimodal_parts([upload], storage)

        assert len(parts) == 1
        assert isinstance(parts[0], str)
        assert "Document content here" in parts[0]
        assert "doc.docx" in parts[0]

    async def test_empty_list_returns_empty(self):
        storage = AsyncMock()

        parts = await _build_multimodal_parts([], storage)

        assert parts == []

    async def test_mixed_files(self):
        img = _make_upload(
            file_id="f1",
            filename="pic.jpg",
            content_type="image/jpeg",
            storage_path="/tmp/pic.jpg",
        )
        txt = _make_upload(
            file_id="f2",
            filename="readme.md",
            content_type="text/markdown",
            extracted_text="# Hello",
            storage_path="/tmp/readme.md",
        )
        storage = AsyncMock()
        storage.retrieve = AsyncMock(return_value=b"\xff\xd8\xff\xe0...")

        parts = await _build_multimodal_parts([img, txt], storage)

        assert len(parts) == 2
        from fireflyframework_genai.types import BinaryContent

        assert isinstance(parts[0], BinaryContent)
        assert isinstance(parts[1], str)
        assert "# Hello" in parts[1]

    async def test_file_without_extracted_text_skipped(self):
        """Non-image files without extracted_text should be skipped entirely."""
        upload = _make_upload(
            file_id="f4",
            filename="data.csv",
            content_type="text/csv",
            extracted_text=None,
            storage_path="/tmp/data.csv",
        )
        storage = AsyncMock()

        parts = await _build_multimodal_parts([upload], storage)

        assert parts == []

    async def test_all_image_content_types_recognized(self):
        """Verify all expected image MIME types are in the constant."""
        expected = {"image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml"}
        assert expected == _IMAGE_CONTENT_TYPES

    async def test_gif_image_returns_binary_content(self):
        upload = _make_upload(
            file_id="f5",
            filename="anim.gif",
            content_type="image/gif",
            storage_path="/tmp/anim.gif",
        )
        storage = AsyncMock()
        storage.retrieve = AsyncMock(return_value=b"GIF89a...")

        parts = await _build_multimodal_parts([upload], storage)

        assert len(parts) == 1
        from fireflyframework_genai.types import BinaryContent

        assert isinstance(parts[0], BinaryContent)
        assert parts[0].media_type == "image/gif"

    async def test_webp_image_returns_binary_content(self):
        upload = _make_upload(
            file_id="f6",
            filename="photo.webp",
            content_type="image/webp",
            storage_path="/tmp/photo.webp",
        )
        storage = AsyncMock()
        storage.retrieve = AsyncMock(return_value=b"RIFF....")

        parts = await _build_multimodal_parts([upload], storage)

        assert len(parts) == 1
        from fireflyframework_genai.types import BinaryContent

        assert isinstance(parts[0], BinaryContent)
        assert parts[0].media_type == "image/webp"
