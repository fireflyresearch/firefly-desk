# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Test knowledge context token budget."""
from __future__ import annotations

from flydesk.agent.prompt import truncate_to_token_budget


def test_under_budget():
    text = "Short text"
    result = truncate_to_token_budget(text, max_tokens=100)
    assert result == text


def test_over_budget_truncates():
    text = "x" * 20000  # ~5000 tokens at 4 chars/token
    result = truncate_to_token_budget(text, max_tokens=1000)
    assert len(result) <= 4000 + 50  # 4 chars/token * 1000 tokens + buffer


def test_zero_budget_returns_empty():
    result = truncate_to_token_budget("hello world", max_tokens=0)
    assert result == ""
