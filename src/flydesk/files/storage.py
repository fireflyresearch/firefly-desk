# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""File storage providers for Firefly Desk."""

from __future__ import annotations

import os
import uuid
from typing import Protocol, runtime_checkable


@runtime_checkable
class FileStorageProvider(Protocol):
    """Protocol for file storage backends."""

    async def store(self, filename: str, content: bytes, content_type: str) -> str:
        """Store a file and return its storage path."""
        ...

    async def retrieve(self, storage_path: str) -> bytes:
        """Retrieve a file's content by its storage path."""
        ...

    async def delete(self, storage_path: str) -> None:
        """Delete a file by its storage path."""
        ...


class LocalFileStorage:
    """Store files on the local filesystem."""

    def __init__(self, base_dir: str = "./uploads") -> None:
        self._base_dir = os.path.abspath(base_dir)
        os.makedirs(self._base_dir, exist_ok=True)

    async def store(self, filename: str, content: bytes, content_type: str) -> str:
        """Store a file locally and return its path."""
        ext = os.path.splitext(filename)[1]
        storage_name = f"{uuid.uuid4()}{ext}"
        path = os.path.join(self._base_dir, storage_name)
        with open(path, "wb") as f:
            f.write(content)
        return path

    async def retrieve(self, storage_path: str) -> bytes:
        """Read a file from local storage."""
        # If storage_path is relative, resolve against base_dir
        full_path = (
            storage_path
            if os.path.isabs(storage_path)
            else os.path.join(self._base_dir, os.path.basename(storage_path))
        )
        with open(full_path, "rb") as f:
            return f.read()

    async def delete(self, storage_path: str) -> None:
        """Delete a file from local storage."""
        full_path = (
            storage_path
            if os.path.isabs(storage_path)
            else os.path.join(self._base_dir, os.path.basename(storage_path))
        )
        if os.path.exists(full_path):
            os.remove(full_path)
