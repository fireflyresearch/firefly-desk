# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""RBAC domain models -- Role and AccessScopes."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AccessScopes(BaseModel):
    """Resource-level access rules attached to a role.

    Each list defines which resources the role may access.
    An **empty list** means unrestricted (all resources accessible),
    preserving backwards compatibility with roles that predate scoping.
    """

    systems: list[str] = Field(default_factory=list)
    """System IDs the role can access (empty = all accessible)."""

    knowledge_tags: list[str] = Field(default_factory=list)
    """Knowledge document tags the role can access (empty = all)."""

    skill_tags: list[str] = Field(default_factory=list)
    """Skill tags the role can access (empty = all)."""

    def can_access_system(self, system_id: str) -> bool:
        """Return True if the role is allowed to use *system_id*."""
        return not self.systems or system_id in self.systems

    def can_access_knowledge(self, doc_tags: list[str]) -> bool:
        """Return True if the role may see a document with *doc_tags*."""
        return not self.knowledge_tags or any(
            t in self.knowledge_tags for t in doc_tags
        )

    def can_access_skill(self, skill_tags: list[str]) -> bool:
        """Return True if the role may use a skill with *skill_tags*."""
        return not self.skill_tags or any(
            t in self.skill_tags for t in skill_tags
        )


class Role(BaseModel):
    """A role that bundles a set of permissions."""

    id: str
    name: str
    display_name: str
    description: str = ""
    permissions: list[str] = Field(default_factory=list)
    access_scopes: AccessScopes = Field(default_factory=AccessScopes)
    is_builtin: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
