# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Pydantic domain models for business process discovery."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ProcessStatus(StrEnum):
    """Lifecycle status of a discovered business process."""

    DISCOVERED = "discovered"
    VERIFIED = "verified"
    MODIFIED = "modified"
    ARCHIVED = "archived"


class ProcessSource(StrEnum):
    """How a business process was created or discovered."""

    AUTO_DISCOVERED = "auto_discovered"
    MANUAL = "manual"
    IMPORTED = "imported"


class ProcessStep(BaseModel):
    """A single step within a business process."""

    id: str
    name: str
    description: str = ""
    step_type: str = ""  # "action", "decision", "wait", etc.
    system_id: str | None = None  # FK to external system catalog
    endpoint_id: str | None = None  # FK to service endpoint catalog
    order: int = 0
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)


class ProcessDependency(BaseModel):
    """Directed edge between two process steps."""

    source_step_id: str
    target_step_id: str
    condition: str | None = None  # optional branching condition


class BusinessProcess(BaseModel):
    """A discovered or manually-defined business process."""

    id: str
    name: str
    description: str = ""
    category: str = ""  # "customer-service", "operations", "hr", etc.
    workspace_id: str | None = None
    steps: list[ProcessStep] = Field(default_factory=list)
    dependencies: list[ProcessDependency] = Field(default_factory=list)
    source: ProcessSource = ProcessSource.AUTO_DISCOVERED
    confidence: float = 0.0  # LLM confidence in discovery
    status: ProcessStatus = ProcessStatus.DISCOVERED
    tags: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
