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


@dataclass
class PromptContext:
    """Context needed to build the system prompt."""

    agent_name: str = "Firefly Desk Assistant"
    company_name: str | None = None
    user_name: str = ""
    user_roles: list[str] = field(default_factory=list)
    user_permissions: list[str] = field(default_factory=list)
    tool_summaries: list[dict[str, str]] = field(default_factory=list)
    knowledge_context: str = ""
    conversation_summary: str = ""


class SystemPromptBuilder:
    """Builds the Desk Agent system prompt from modular sections."""

    def build(self, context: PromptContext) -> str:
        """Assemble the full system prompt."""
        sections = [
            self._identity_section(context),
            self._user_context_section(context),
            self._available_tools_section(context),
            self._widget_instructions_section(),
            self._behavioral_guidelines_section(),
        ]
        # Optional per-turn sections
        if context.knowledge_context:
            sections.append(self._knowledge_context_section(context))
        if context.conversation_summary:
            sections.append(self._conversation_history_section(context))

        return "\n\n".join(sections)

    @staticmethod
    def _identity_section(context: PromptContext) -> str:
        company = f" for {context.company_name}" if context.company_name else ""
        return (
            f"# Identity\n\n"
            f"You are {context.agent_name}{company}. "
            f"You are a backoffice operations assistant that helps users interact with "
            f"backend systems through natural conversation. You have access to specific "
            f"tools that call real APIs on the user's behalf."
        )

    @staticmethod
    def _user_context_section(context: PromptContext) -> str:
        roles_str = ", ".join(context.user_roles) if context.user_roles else "none"
        return (
            f"# Current User\n\n"
            f"- Name: {context.user_name}\n"
            f"- Roles: {roles_str}\n"
            f"- You may only use tools this user has permission to access."
        )

    @staticmethod
    def _available_tools_section(context: PromptContext) -> str:
        if not context.tool_summaries:
            return "# Available Tools\n\nNo tools are currently available."

        lines = ["# Available Tools\n"]
        for tool in context.tool_summaries:
            name = tool.get("name", "Unknown")
            description = tool.get("description", "")
            risk = tool.get("risk_level", "read")
            lines.append(f"- **{name}** ({risk}): {description}")

        return "\n".join(lines)

    @staticmethod
    def _widget_instructions_section() -> str:
        return (
            "# Widget Output\n\n"
            "When presenting structured data, embed widget directives in your markdown response.\n\n"
            "Format:\n"
            "```\n"
            ':::widget{type="widget-type" panel=true}\n'
            '{"prop": "value"}\n'
            ":::\n"
            "```\n\n"
            "Available widget types: status-badge, entity-card, data-table, key-value, "
            "alert, timeline, diff-viewer, confirmation.\n\n"
            "Use `panel=true` for detailed views that open in the side panel.\n"
            "Use `inline=true` (default) for small widgets embedded in chat.\n"
            "Use `blocking=true` with `action=\"action-name\"` for confirmations that "
            "require user approval before proceeding."
        )

    @staticmethod
    def _behavioral_guidelines_section() -> str:
        return (
            "# Guidelines\n\n"
            "- Be concise and professional. No emojis.\n"
            "- Always explain what you are about to do before calling a tool.\n"
            "- For read operations, proceed directly.\n"
            "- For high-risk writes or destructive operations, emit a confirmation widget "
            "and wait for user approval.\n"
            "- If a tool call fails, explain the error clearly and suggest next steps.\n"
            "- Present data using appropriate widgets rather than raw text when possible.\n"
            "- If you are unsure about the user's intent, ask for clarification."
        )

    @staticmethod
    def _knowledge_context_section(context: PromptContext) -> str:
        return f"# Relevant Context\n\n{context.knowledge_context}"

    @staticmethod
    def _conversation_history_section(context: PromptContext) -> str:
        return f"# Recent Conversation\n\n{context.conversation_summary}"
