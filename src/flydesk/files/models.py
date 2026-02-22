# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Pydantic domain models for file uploads."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FileUpload(BaseModel):
    """Domain model for a file upload."""

    id: str
    conversation_id: str | None = None
    user_id: str
    filename: str
    content_type: str
    file_size: int
    storage_path: str
    storage_backend: str = "local"
    extracted_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
