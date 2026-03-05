# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for workflow conditional branching."""

from __future__ import annotations

from flydesk.workflows.engine import WorkflowEngine
from flydesk.workflows.models import StepType


def test_condition_step_type_exists():
    assert hasattr(StepType, "CONDITION")
    assert StepType.CONDITION == "condition"


def test_loop_step_type_exists():
    assert hasattr(StepType, "LOOP")
    assert StepType.LOOP == "loop"


def test_check_condition_eq():
    state = {"approval_status": "approved"}
    condition = {
        "field": "state.approval_status",
        "operator": "eq",
        "value": "approved",
        "then_step": 5,
        "else_step": 7,
    }
    result = WorkflowEngine._check_condition(state, condition)
    assert result == 5


def test_check_condition_ne():
    state = {"approval_status": "rejected"}
    condition = {
        "field": "state.approval_status",
        "operator": "ne",
        "value": "approved",
        "then_step": 5,
        "else_step": 7,
    }
    result = WorkflowEngine._check_condition(state, condition)
    assert result == 5


def test_check_condition_gt():
    state = {"score": 85}
    condition = {
        "field": "state.score",
        "operator": "gt",
        "value": 80,
        "then_step": 3,
        "else_step": 6,
    }
    result = WorkflowEngine._check_condition(state, condition)
    assert result == 3


def test_check_condition_in():
    state = {"role": "admin"}
    condition = {
        "field": "state.role",
        "operator": "in",
        "value": ["admin", "superadmin"],
        "then_step": 2,
        "else_step": 4,
    }
    result = WorkflowEngine._check_condition(state, condition)
    assert result == 2


def test_check_condition_contains():
    state = {"tags": ["urgent", "billing"]}
    condition = {
        "field": "state.tags",
        "operator": "contains",
        "value": "urgent",
        "then_step": 1,
        "else_step": 9,
    }
    result = WorkflowEngine._check_condition(state, condition)
    assert result == 1


def test_check_condition_else_branch():
    state = {"score": 50}
    condition = {
        "field": "state.score",
        "operator": "gt",
        "value": 80,
        "then_step": 3,
        "else_step": 6,
    }
    result = WorkflowEngine._check_condition(state, condition)
    assert result == 6
