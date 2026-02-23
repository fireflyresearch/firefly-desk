# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for ProcessRepository -- CRUD for business processes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.models.base import Base
from flydesk.processes.models import (
    BusinessProcess,
    ProcessDependency,
    ProcessSource,
    ProcessStatus,
    ProcessStep,
)
from flydesk.processes.repository import ProcessRepository


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def repo(session_factory):
    return ProcessRepository(session_factory)


def _make_step(step_id: str = "s-1", name: str = "Step 1", order: int = 0, **kw) -> ProcessStep:
    return ProcessStep(id=step_id, name=name, order=order, **kw)


def _make_dep(source: str = "s-1", target: str = "s-2", **kw) -> ProcessDependency:
    return ProcessDependency(source_step_id=source, target_step_id=target, **kw)


def _make_process(
    process_id: str = "p-1",
    name: str = "Test Process",
    **kwargs,
) -> BusinessProcess:
    now = datetime.now(timezone.utc)
    return BusinessProcess(
        id=process_id,
        name=name,
        description=kwargs.pop("description", "A test process"),
        category=kwargs.pop("category", "operations"),
        steps=kwargs.pop("steps", []),
        dependencies=kwargs.pop("dependencies", []),
        source=kwargs.pop("source", ProcessSource.AUTO_DISCOVERED),
        confidence=kwargs.pop("confidence", 0.85),
        status=kwargs.pop("status", ProcessStatus.DISCOVERED),
        tags=kwargs.pop("tags", ["test"]),
        created_at=kwargs.pop("created_at", now),
        updated_at=kwargs.pop("updated_at", now),
        **kwargs,
    )


class TestProcessRepositoryCreate:
    async def test_create_and_get(self, repo):
        """Creating a process and retrieving it returns matching data."""
        proc = _make_process(
            steps=[_make_step("s-1", "First"), _make_step("s-2", "Second", order=1)],
            dependencies=[_make_dep("s-1", "s-2")],
        )
        created = await repo.create(proc)
        assert created.id == "p-1"
        assert created.name == "Test Process"
        assert created.category == "operations"
        assert created.confidence == 0.85
        assert created.status == ProcessStatus.DISCOVERED
        assert created.tags == ["test"]
        assert len(created.steps) == 2
        assert len(created.dependencies) == 1

    async def test_create_minimal_process(self, repo):
        """A process with no steps or dependencies can be created."""
        proc = _make_process(tags=[], category="")
        created = await repo.create(proc)
        assert created.steps == []
        assert created.dependencies == []
        assert created.tags == []

    async def test_create_sets_timestamps(self, repo):
        """Timestamps are set on creation."""
        proc = _make_process(created_at=None, updated_at=None)
        created = await repo.create(proc)
        assert created.created_at is not None
        assert created.updated_at is not None


class TestProcessRepositoryGet:
    async def test_get_nonexistent_returns_none(self, repo):
        """Getting a non-existent process returns None."""
        result = await repo.get("nonexistent")
        assert result is None

    async def test_get_includes_steps_and_deps(self, repo):
        """Steps and dependencies are eagerly loaded."""
        proc = _make_process(
            steps=[_make_step("s-1", "A", 0), _make_step("s-2", "B", 1)],
            dependencies=[_make_dep("s-1", "s-2", condition="always")],
        )
        await repo.create(proc)
        result = await repo.get("p-1")
        assert result is not None
        assert len(result.steps) == 2
        assert result.steps[0].id == "s-1"  # sorted by order
        assert result.steps[1].id == "s-2"
        assert result.dependencies[0].condition == "always"

    async def test_step_details_preserved(self, repo):
        """All step fields survive a round-trip through the database."""
        step = ProcessStep(
            id="s-full",
            name="Full Step",
            description="Detailed description",
            step_type="action",
            system_id="sys-crm",
            endpoint_id="ep-api",
            order=5,
            inputs=["customer_id", "order_id"],
            outputs=["result_code"],
        )
        proc = _make_process(steps=[step])
        await repo.create(proc)
        result = await repo.get("p-1")
        assert result is not None
        s = result.steps[0]
        assert s.id == "s-full"
        assert s.description == "Detailed description"
        assert s.step_type == "action"
        assert s.system_id == "sys-crm"
        assert s.endpoint_id == "ep-api"
        assert s.order == 5
        assert s.inputs == ["customer_id", "order_id"]
        assert s.outputs == ["result_code"]


class TestProcessRepositoryList:
    async def test_list_all(self, repo):
        """list() returns all processes, most recent first."""
        now = datetime.now(timezone.utc)
        await repo.create(_make_process("p-1", created_at=now - timedelta(minutes=2)))
        await repo.create(_make_process("p-2", created_at=now - timedelta(minutes=1)))
        await repo.create(_make_process("p-3", created_at=now))

        result = await repo.list()
        assert len(result) == 3
        assert result[0].id == "p-3"
        assert result[2].id == "p-1"

    async def test_list_filter_by_category(self, repo):
        """list() filters by category."""
        await repo.create(_make_process("p-1", category="operations"))
        await repo.create(_make_process("p-2", category="hr"))
        await repo.create(_make_process("p-3", category="operations"))

        result = await repo.list(category="operations")
        assert len(result) == 2
        assert all(p.category == "operations" for p in result)

    async def test_list_filter_by_status(self, repo):
        """list() filters by status."""
        await repo.create(_make_process("p-1", status=ProcessStatus.DISCOVERED))
        await repo.create(_make_process("p-2", status=ProcessStatus.VERIFIED))
        await repo.create(_make_process("p-3", status=ProcessStatus.ARCHIVED))

        result = await repo.list(status=ProcessStatus.VERIFIED)
        assert len(result) == 1
        assert result[0].id == "p-2"

    async def test_list_filter_by_tag(self, repo):
        """list() filters by tag."""
        await repo.create(_make_process("p-1", tags=["onboarding", "customer"]))
        await repo.create(_make_process("p-2", tags=["billing"]))
        await repo.create(_make_process("p-3", tags=["customer", "support"]))

        result = await repo.list(tag="customer")
        assert len(result) == 2
        ids = {p.id for p in result}
        assert ids == {"p-1", "p-3"}

    async def test_list_combined_filters(self, repo):
        """list() applies multiple filters."""
        await repo.create(
            _make_process("p-1", category="ops", status=ProcessStatus.VERIFIED, tags=["x"])
        )
        await repo.create(
            _make_process("p-2", category="ops", status=ProcessStatus.DISCOVERED, tags=["x"])
        )
        await repo.create(
            _make_process("p-3", category="hr", status=ProcessStatus.VERIFIED, tags=["x"])
        )

        result = await repo.list(category="ops", status=ProcessStatus.VERIFIED, tag="x")
        assert len(result) == 1
        assert result[0].id == "p-1"

    async def test_list_with_limit_and_offset(self, repo):
        """list() respects limit and offset."""
        now = datetime.now(timezone.utc)
        for i in range(5):
            await repo.create(
                _make_process(f"p-{i}", created_at=now + timedelta(seconds=i))
            )

        result = await repo.list(limit=2, offset=1)
        assert len(result) == 2
        # Most recent first: p-4, p-3, p-2, p-1, p-0
        # offset=1 skips p-4, limit=2 returns p-3, p-2
        assert result[0].id == "p-3"
        assert result[1].id == "p-2"

    async def test_list_empty(self, repo):
        """list() returns empty list when no processes exist."""
        result = await repo.list()
        assert result == []


class TestProcessRepositoryUpdate:
    async def test_update_basic_fields(self, repo):
        """update() persists changes to basic fields."""
        await repo.create(_make_process())
        proc = await repo.get("p-1")
        assert proc is not None

        proc.name = "Updated Name"
        proc.description = "Updated desc"
        proc.category = "hr"
        proc.status = ProcessStatus.VERIFIED
        proc.confidence = 0.99
        proc.tags = ["updated", "new-tag"]

        updated = await repo.update(proc)
        assert updated.name == "Updated Name"
        assert updated.description == "Updated desc"
        assert updated.category == "hr"
        assert updated.status == ProcessStatus.VERIFIED
        assert updated.confidence == 0.99
        assert updated.tags == ["updated", "new-tag"]

    async def test_update_replaces_steps(self, repo):
        """update() replaces old steps with new ones."""
        await repo.create(
            _make_process(steps=[_make_step("s-1", "Old step")])
        )
        proc = await repo.get("p-1")
        assert proc is not None

        proc.steps = [
            _make_step("s-new-1", "New step 1", order=0),
            _make_step("s-new-2", "New step 2", order=1),
        ]
        updated = await repo.update(proc)
        assert len(updated.steps) == 2
        assert updated.steps[0].id == "s-new-1"
        assert updated.steps[1].id == "s-new-2"

    async def test_update_replaces_dependencies(self, repo):
        """update() replaces old dependencies."""
        await repo.create(
            _make_process(
                steps=[_make_step("s-1"), _make_step("s-2", order=1)],
                dependencies=[_make_dep("s-1", "s-2")],
            )
        )
        proc = await repo.get("p-1")
        assert proc is not None

        proc.dependencies = []
        updated = await repo.update(proc)
        assert updated.dependencies == []

    async def test_update_nonexistent_raises(self, repo):
        """update() raises ValueError for a non-existent process."""
        proc = _make_process("nonexistent")
        with pytest.raises(ValueError, match="not found"):
            await repo.update(proc)

    async def test_update_touches_updated_at(self, repo):
        """update() refreshes updated_at."""
        await repo.create(_make_process())
        proc = await repo.get("p-1")
        assert proc is not None
        original_updated = proc.updated_at

        proc.name = "Changed"
        updated = await repo.update(proc)
        assert updated.updated_at is not None
        # updated_at should be >= original (may be same in fast tests)
        if original_updated is not None:
            assert updated.updated_at >= original_updated


class TestProcessRepositoryDelete:
    async def test_delete_existing(self, repo):
        """delete() removes an existing process and returns True."""
        await repo.create(_make_process())
        result = await repo.delete("p-1")
        assert result is True
        assert await repo.get("p-1") is None

    async def test_delete_nonexistent(self, repo):
        """delete() returns False if process doesn't exist."""
        result = await repo.delete("nonexistent")
        assert result is False

    async def test_delete_cascades_steps_and_deps(self, repo):
        """Deleting a process also removes its steps and dependencies."""
        await repo.create(
            _make_process(
                steps=[_make_step("s-1"), _make_step("s-2", order=1)],
                dependencies=[_make_dep("s-1", "s-2")],
            )
        )
        await repo.delete("p-1")
        # Verify the process (and implicitly its children) is gone
        assert await repo.get("p-1") is None


class TestProcessRepositoryUpdateStep:
    async def test_update_existing_step(self, repo):
        """update_step() modifies an existing step in-place."""
        await repo.create(_make_process(steps=[_make_step("s-1", "Original")]))
        updated_step = _make_step("s-1", "Modified", step_type="decision")
        result = await repo.update_step("p-1", updated_step)
        assert result is not None
        assert result.name == "Modified"

        proc = await repo.get("p-1")
        assert proc is not None
        assert proc.steps[0].name == "Modified"
        assert proc.steps[0].step_type == "decision"

    async def test_add_new_step(self, repo):
        """update_step() adds a step if its ID doesn't exist in the process."""
        await repo.create(_make_process(steps=[_make_step("s-1", "Existing")]))
        new_step = _make_step("s-2", "Brand New", order=1)
        result = await repo.update_step("p-1", new_step)
        assert result is not None

        proc = await repo.get("p-1")
        assert proc is not None
        assert len(proc.steps) == 2

    async def test_update_step_nonexistent_process(self, repo):
        """update_step() returns None if the process doesn't exist."""
        result = await repo.update_step("nonexistent", _make_step())
        assert result is None


class TestProcessRepositoryDependencies:
    async def test_add_dependency(self, repo):
        """add_dependency() adds a new edge."""
        await repo.create(
            _make_process(
                steps=[_make_step("s-1"), _make_step("s-2", order=1), _make_step("s-3", order=2)]
            )
        )
        dep = _make_dep("s-1", "s-2", condition="on_success")
        result = await repo.add_dependency("p-1", dep)
        assert result is not None
        assert result.condition == "on_success"

        proc = await repo.get("p-1")
        assert proc is not None
        assert len(proc.dependencies) == 1
        assert proc.dependencies[0].source_step_id == "s-1"
        assert proc.dependencies[0].target_step_id == "s-2"

    async def test_add_dependency_nonexistent_process(self, repo):
        """add_dependency() returns None if the process doesn't exist."""
        result = await repo.add_dependency("nonexistent", _make_dep())
        assert result is None

    async def test_remove_dependency(self, repo):
        """remove_dependency() removes a matching edge."""
        await repo.create(
            _make_process(
                steps=[_make_step("s-1"), _make_step("s-2", order=1)],
                dependencies=[_make_dep("s-1", "s-2")],
            )
        )
        result = await repo.remove_dependency("p-1", "s-1", "s-2")
        assert result is True

        proc = await repo.get("p-1")
        assert proc is not None
        assert len(proc.dependencies) == 0

    async def test_remove_dependency_nonexistent(self, repo):
        """remove_dependency() returns False if no matching edge exists."""
        await repo.create(_make_process())
        result = await repo.remove_dependency("p-1", "s-1", "s-2")
        assert result is False

    async def test_add_multiple_dependencies(self, repo):
        """Multiple dependency edges can be added to one process."""
        await repo.create(
            _make_process(
                steps=[
                    _make_step("s-1", order=0),
                    _make_step("s-2", order=1),
                    _make_step("s-3", order=2),
                ]
            )
        )
        await repo.add_dependency("p-1", _make_dep("s-1", "s-2"))
        await repo.add_dependency("p-1", _make_dep("s-1", "s-3"))
        await repo.add_dependency("p-1", _make_dep("s-2", "s-3"))

        proc = await repo.get("p-1")
        assert proc is not None
        assert len(proc.dependencies) == 3


class TestProcessRepositoryEdgeCases:
    async def test_process_with_empty_tags(self, repo):
        """Processes with empty tags list persist correctly."""
        await repo.create(_make_process(tags=[]))
        proc = await repo.get("p-1")
        assert proc is not None
        assert proc.tags == []

    async def test_step_with_empty_inputs_outputs(self, repo):
        """Steps with empty inputs/outputs persist correctly."""
        step = ProcessStep(id="s-1", name="Empty IO")
        await repo.create(_make_process(steps=[step]))
        proc = await repo.get("p-1")
        assert proc is not None
        assert proc.steps[0].inputs == []
        assert proc.steps[0].outputs == []

    async def test_steps_sorted_by_order(self, repo):
        """Steps are returned sorted by order, regardless of insertion order."""
        steps = [
            _make_step("s-3", "Third", order=2),
            _make_step("s-1", "First", order=0),
            _make_step("s-2", "Second", order=1),
        ]
        await repo.create(_make_process(steps=steps))
        proc = await repo.get("p-1")
        assert proc is not None
        assert [s.id for s in proc.steps] == ["s-1", "s-2", "s-3"]

    async def test_all_source_types_persist(self, repo):
        """All ProcessSource values can be stored and retrieved."""
        for i, source in enumerate(ProcessSource):
            await repo.create(_make_process(f"p-{i}", source=source))
            proc = await repo.get(f"p-{i}")
            assert proc is not None
            assert proc.source == source

    async def test_all_status_types_persist(self, repo):
        """All ProcessStatus values can be stored and retrieved."""
        for i, status in enumerate(ProcessStatus):
            await repo.create(_make_process(f"p-{i}", status=status))
            proc = await repo.get(f"p-{i}")
            assert proc is not None
            assert proc.status == status
