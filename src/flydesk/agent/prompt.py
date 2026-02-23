# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""System prompt builder for the Desk Agent."""

from __future__ import annotations

from dataclasses import dataclass, field

from fireflyframework_genai.prompts import PromptRegistry


@dataclass
class PromptContext:
    """Context needed to build the system prompt."""

    agent_name: str = "Ember"
    company_name: str | None = None
    user_name: str = ""
    user_roles: list[str] = field(default_factory=list)
    user_permissions: list[str] = field(default_factory=list)
    user_department: str = ""
    user_title: str = ""
    tool_summaries: list[dict[str, str]] = field(default_factory=list)
    knowledge_context: str = ""
    conversation_summary: str = ""
    file_context: str = ""


class SystemPromptBuilder:
    """Builds the Desk Agent system prompt from Jinja2 templates via :class:`PromptRegistry`."""

    def __init__(self, registry: PromptRegistry) -> None:
        self._registry = registry

    def build(self, context: PromptContext) -> str:
        """Assemble the full system prompt."""
        # Identity -- Ember gets the rich personality template
        if context.agent_name == "Ember":
            identity = self._registry.get("identity_ember").render(
                agent_name=context.agent_name,
                company_name=context.company_name,
            )
        else:
            identity = self._registry.get("identity").render(
                agent_name=context.agent_name,
                company_name=context.company_name,
            )

        user_ctx = self._render_user_context(context)
        tools = self._registry.get("available_tools").render(
            tool_summaries=context.tool_summaries,
        )
        widgets = self._registry.get("widget_instructions").render()
        guidelines = self._registry.get("behavioral_guidelines").render()

        sections = [identity, user_ctx, tools, widgets, guidelines]

        # Optional per-turn sections
        if context.knowledge_context:
            sections.append(
                self._registry.get("knowledge_context").render(
                    knowledge_context=context.knowledge_context,
                )
            )
        if context.file_context:
            sections.append(
                self._registry.get("file_context").render(
                    file_context=context.file_context,
                )
            )
        if context.conversation_summary:
            sections.append(
                self._registry.get("conversation_history").render(
                    conversation_summary=context.conversation_summary,
                )
            )

        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # Convenience method kept for callers that need a single section
    # ------------------------------------------------------------------

    def _user_context_section(self, context: PromptContext) -> str:
        """Render the user-context section from the template."""
        return self._render_user_context(context)

    def _render_user_context(self, context: PromptContext) -> str:
        """Render user context via the registry template."""
        return self._registry.get("user_context").render(
            user_name=context.user_name,
            user_roles=context.user_roles,
            user_department=context.user_department,
            user_title=context.user_title,
        )
