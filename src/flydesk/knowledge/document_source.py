# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Provider protocols, data classes, and factory for document sources."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Importable file extensions
# ---------------------------------------------------------------------------

IMPORTABLE_EXTENSIONS: frozenset[str] = frozenset(
    {".md", ".txt", ".json", ".yaml", ".yml", ".pdf", ".docx"}
)


# ---------------------------------------------------------------------------
# Blob Storage data classes
# ---------------------------------------------------------------------------


@dataclass
class StorageContainer:
    name: str
    region: str = ""


@dataclass
class StorageObject:
    key: str
    size: int
    last_modified: str
    content_type: str = ""


# ---------------------------------------------------------------------------
# Drive data classes
# ---------------------------------------------------------------------------


@dataclass
class DriveInfo:
    id: str
    name: str
    type: str = ""  # "personal", "business", "sharepoint", "shared"


@dataclass
class DriveItem:
    id: str
    name: str
    path: str
    is_folder: bool
    size: int = 0
    modified_at: str = ""
    mime_type: str = ""


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class BlobStorageProvider(Protocol):
    """Protocol for blob/object storage providers (S3, Azure Blob, GCS)."""

    async def validate_credentials(self) -> bool: ...
    async def list_containers(self) -> list[StorageContainer]: ...
    async def list_objects(self, container: str, prefix: str = "") -> list[StorageObject]: ...
    async def get_object_content(self, container: str, key: str) -> bytes: ...
    async def aclose(self) -> None: ...


@runtime_checkable
class DriveProvider(Protocol):
    """Protocol for drive providers (OneDrive, SharePoint, Google Drive)."""

    async def validate_credentials(self) -> bool: ...
    async def list_drives(self) -> list[DriveInfo]: ...
    async def list_items(self, drive_id: str, folder_id: str = "") -> list[DriveItem]: ...
    async def get_file_content(self, drive_id: str, item_id: str) -> bytes: ...
    async def aclose(self) -> None: ...


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class DocumentSourceFactory:
    """Registry and factory for document source adapters."""

    _registry: dict[str, type] = {}

    @classmethod
    def register(cls, source_type: str, adapter_cls: type) -> None:
        """Register an adapter class for a source type."""
        cls._registry[source_type] = adapter_cls

    @classmethod
    def create(cls, source_type: str, config: dict) -> BlobStorageProvider | DriveProvider:
        """Create a provider instance from the registry."""
        adapter_cls = cls._registry.get(source_type)
        if adapter_cls is None:
            raise ValueError(f"Unknown source type: {source_type!r}. Registered: {list(cls._registry)}")
        return adapter_cls(config)

    @classmethod
    def registered_types(cls) -> list[str]:
        """Return all registered source types."""
        return list(cls._registry.keys())
