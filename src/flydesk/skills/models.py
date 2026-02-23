# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Pydantic domain model for Skills."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class Skill(BaseModel):
    """A reusable skill definition."""

    id: str
    name: str
    description: str = ""
    content: str = ""
    tags: list[str] = []
    active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
