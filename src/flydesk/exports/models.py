# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Pydantic domain models for the export subsystem."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ExportFormat(StrEnum):
    """Supported export file formats."""

    CSV = "csv"
    JSON = "json"
    PDF = "pdf"


class ExportStatus(StrEnum):
    """Lifecycle status of an export job."""

    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class ExportRecord(BaseModel):
    """Domain model for a single export job."""

    id: str
    user_id: str
    format: ExportFormat
    template_id: str | None = None
    title: str
    description: str | None = None
    status: ExportStatus = ExportStatus.PENDING
    file_path: str | None = None
    file_size: int | None = None
    row_count: int | None = None
    error: str | None = None
    source_data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    completed_at: datetime | None = None


class ExportTemplate(BaseModel):
    """A reusable template that controls export formatting."""

    id: str
    name: str
    format: ExportFormat
    column_mapping: dict[str, str] = Field(default_factory=dict)
    header_text: str | None = None
    footer_text: str | None = None
    is_system: bool = False
    created_at: datetime | None = None
