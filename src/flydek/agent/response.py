# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Agent response model for a single turn."""

from __future__ import annotations

from dataclasses import dataclass, field

from flydek.widgets.schema import WidgetDirective


@dataclass
class AgentResponse:
    """The result of a single agent turn."""

    text: str
    """Full response text with widget directives stripped."""

    widgets: list[WidgetDirective] = field(default_factory=list)
    """Parsed widget directives extracted from the LLM output."""

    raw_text: str = ""
    """Original LLM output including widget directives."""

    conversation_id: str = ""
    """The conversation this turn belongs to."""

    turn_id: str = ""
    """Unique identifier for this specific turn."""
