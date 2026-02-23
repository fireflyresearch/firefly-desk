# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for process discovery domain models."""

from __future__ import annotations

from datetime import datetime, timezone

from flydesk.processes.models import (
    BusinessProcess,
    ProcessDependency,
    ProcessSource,
    ProcessStatus,
    ProcessStep,
)


class TestProcessStatus:
    def test_values(self):
        assert ProcessStatus.DISCOVERED == "discovered"
        assert ProcessStatus.VERIFIED == "verified"
        assert ProcessStatus.MODIFIED == "modified"
        assert ProcessStatus.ARCHIVED == "archived"

    def test_str_conversion(self):
        assert ProcessStatus("discovered") == ProcessStatus.DISCOVERED


class TestProcessSource:
    def test_values(self):
        assert ProcessSource.AUTO_DISCOVERED == "auto_discovered"
        assert ProcessSource.MANUAL == "manual"
        assert ProcessSource.IMPORTED == "imported"

    def test_str_conversion(self):
        assert ProcessSource("manual") == ProcessSource.MANUAL


class TestProcessStep:
    def test_minimal_step(self):
        step = ProcessStep(id="s-1", name="Submit form")
        assert step.id == "s-1"
        assert step.name == "Submit form"
        assert step.description == ""
        assert step.step_type == ""
        assert step.system_id is None
        assert step.endpoint_id is None
        assert step.order == 0
        assert step.inputs == []
        assert step.outputs == []

    def test_full_step(self):
        step = ProcessStep(
            id="s-2",
            name="Call API",
            description="Calls the order API",
            step_type="action",
            system_id="sys-1",
            endpoint_id="ep-1",
            order=3,
            inputs=["order_id"],
            outputs=["confirmation"],
        )
        assert step.step_type == "action"
        assert step.system_id == "sys-1"
        assert step.endpoint_id == "ep-1"
        assert step.order == 3
        assert step.inputs == ["order_id"]
        assert step.outputs == ["confirmation"]

    def test_serialization_roundtrip(self):
        step = ProcessStep(id="s-1", name="Step", inputs=["a"], outputs=["b"])
        data = step.model_dump()
        restored = ProcessStep.model_validate(data)
        assert restored == step


class TestProcessDependency:
    def test_minimal_dependency(self):
        dep = ProcessDependency(source_step_id="s-1", target_step_id="s-2")
        assert dep.source_step_id == "s-1"
        assert dep.target_step_id == "s-2"
        assert dep.condition is None

    def test_conditional_dependency(self):
        dep = ProcessDependency(
            source_step_id="s-1", target_step_id="s-3", condition="approved == true"
        )
        assert dep.condition == "approved == true"

    def test_serialization_roundtrip(self):
        dep = ProcessDependency(source_step_id="s-1", target_step_id="s-2", condition="x > 5")
        data = dep.model_dump()
        restored = ProcessDependency.model_validate(data)
        assert restored == dep


class TestBusinessProcess:
    def test_minimal_process(self):
        proc = BusinessProcess(id="p-1", name="Order Fulfillment")
        assert proc.id == "p-1"
        assert proc.name == "Order Fulfillment"
        assert proc.description == ""
        assert proc.category == ""
        assert proc.steps == []
        assert proc.dependencies == []
        assert proc.source == ProcessSource.AUTO_DISCOVERED
        assert proc.confidence == 0.0
        assert proc.status == ProcessStatus.DISCOVERED
        assert proc.tags == []
        assert proc.created_at is None
        assert proc.updated_at is None

    def test_full_process(self):
        now = datetime.now(timezone.utc)
        proc = BusinessProcess(
            id="p-2",
            name="Customer Onboarding",
            description="End-to-end onboarding flow",
            category="customer-service",
            steps=[
                ProcessStep(id="s-1", name="Receive application", order=0),
                ProcessStep(id="s-2", name="Verify identity", order=1),
            ],
            dependencies=[
                ProcessDependency(source_step_id="s-1", target_step_id="s-2"),
            ],
            source=ProcessSource.MANUAL,
            confidence=0.95,
            status=ProcessStatus.VERIFIED,
            tags=["onboarding", "customer"],
            created_at=now,
            updated_at=now,
        )
        assert proc.category == "customer-service"
        assert len(proc.steps) == 2
        assert len(proc.dependencies) == 1
        assert proc.source == ProcessSource.MANUAL
        assert proc.confidence == 0.95
        assert proc.status == ProcessStatus.VERIFIED
        assert proc.tags == ["onboarding", "customer"]

    def test_defaults_are_independent(self):
        """Mutable defaults (lists) should not be shared between instances."""
        p1 = BusinessProcess(id="p-1", name="A")
        p2 = BusinessProcess(id="p-2", name="B")
        p1.tags.append("x")
        assert p2.tags == []

    def test_serialization_roundtrip(self):
        now = datetime.now(timezone.utc)
        proc = BusinessProcess(
            id="p-1",
            name="Test",
            steps=[ProcessStep(id="s-1", name="Step 1")],
            dependencies=[ProcessDependency(source_step_id="s-1", target_step_id="s-2")],
            tags=["tag1"],
            created_at=now,
            updated_at=now,
        )
        data = proc.model_dump()
        restored = BusinessProcess.model_validate(data)
        assert restored == proc
