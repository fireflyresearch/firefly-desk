# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""RBAC domain model -- Role."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Role(BaseModel):
    """A role that bundles a set of permissions."""

    id: str
    name: str
    display_name: str
    description: str = ""
    permissions: list[str] = Field(default_factory=list)
    is_builtin: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
