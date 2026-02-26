# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Pydantic domain models for workspaces."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Workspace(BaseModel):
    id: str
    name: str
    description: str = ""
    icon: str = "folder"
    color: str = "#6366f1"
    is_system: bool = False
    roles: list[str] = Field(default_factory=list)
    users: list[str] = Field(default_factory=list)


class CreateWorkspace(BaseModel):
    name: str
    description: str = ""
    icon: str = "folder"
    color: str = "#6366f1"
    roles: list[str] = Field(default_factory=list)
    users: list[str] = Field(default_factory=list)


class UpdateWorkspace(BaseModel):
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    roles: list[str] | None = None
    users: list[str] | None = None
