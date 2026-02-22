# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the Desk Agent system prompt builder."""

from __future__ import annotations

from flydek.agent.prompt import PromptContext, SystemPromptBuilder


class TestSystemPromptBuilder:
    """Tests for SystemPromptBuilder."""

    def setup_method(self):
        self.builder = SystemPromptBuilder()

    def test_build_includes_all_base_sections(self):
        """Identity, User, Tools, Widget, and Guidelines sections are all present."""
        ctx = PromptContext(
            agent_name="Test Agent",
            user_name="Alice",
            user_roles=["admin"],
        )
        prompt = self.builder.build(ctx)

        assert "# Identity" in prompt
        assert "# Current User" in prompt
        assert "# Available Tools" in prompt
        assert "# Widget Output" in prompt
        assert "# Guidelines" in prompt

    def test_identity_section_with_company(self):
        """Company name is included when set."""
        ctx = PromptContext(
            agent_name="Desk Bot",
            company_name="Acme Corp",
        )
        prompt = self.builder.build(ctx)

        assert "Desk Bot for Acme Corp" in prompt

    def test_identity_section_without_company(self):
        """No company text when company_name is None."""
        ctx = PromptContext(
            agent_name="Desk Bot",
            company_name=None,
        )
        prompt = self.builder.build(ctx)

        assert "Desk Bot." in prompt or "Desk Bot. You are" in prompt
        assert " for " not in prompt.split("# Current User")[0].split("You are Desk Bot")[1]

    def test_user_context_includes_roles(self):
        """Roles are listed in the user context section."""
        ctx = PromptContext(
            user_name="Bob",
            user_roles=["billing-admin", "support"],
        )
        prompt = self.builder.build(ctx)

        assert "Name: Bob" in prompt
        assert "billing-admin" in prompt
        assert "support" in prompt

    def test_available_tools_listed(self):
        """Each tool name and description appears in the prompt."""
        ctx = PromptContext(
            tool_summaries=[
                {"name": "lookup-customer", "description": "Find a customer by ID", "risk_level": "read"},
                {"name": "update-email", "description": "Change email address", "risk_level": "write"},
            ],
        )
        prompt = self.builder.build(ctx)

        assert "lookup-customer" in prompt
        assert "Find a customer by ID" in prompt
        assert "(read)" in prompt
        assert "update-email" in prompt
        assert "Change email address" in prompt
        assert "(write)" in prompt

    def test_no_tools_message(self):
        """'No tools' message appears when tool_summaries is empty."""
        ctx = PromptContext(tool_summaries=[])
        prompt = self.builder.build(ctx)

        assert "No tools are currently available" in prompt

    def test_knowledge_context_included_when_set(self):
        """Knowledge context section appears when knowledge_context is non-empty."""
        ctx = PromptContext(
            knowledge_context="Customer #42 has an open billing dispute.",
        )
        prompt = self.builder.build(ctx)

        assert "# Relevant Context" in prompt
        assert "Customer #42 has an open billing dispute." in prompt

    def test_knowledge_context_excluded_when_empty(self):
        """Knowledge context section is omitted when knowledge_context is empty."""
        ctx = PromptContext(knowledge_context="")
        prompt = self.builder.build(ctx)

        assert "# Relevant Context" not in prompt

    def test_widget_instructions_present(self):
        """Widget directive format is documented in the prompt."""
        ctx = PromptContext()
        prompt = self.builder.build(ctx)

        assert ':::widget{type="widget-type"' in prompt
        assert "status-badge" in prompt
        assert "data-table" in prompt
        assert "confirmation" in prompt
        assert "panel=true" in prompt
        assert "blocking=true" in prompt

    def test_behavioral_guidelines_no_emojis(self):
        """The 'No emojis' rule is present in the guidelines."""
        ctx = PromptContext()
        prompt = self.builder.build(ctx)

        assert "No emojis" in prompt

    def test_conversation_summary_included_when_set(self):
        """Conversation history section appears when conversation_summary is non-empty."""
        ctx = PromptContext(
            conversation_summary="User asked about invoice #100.",
        )
        prompt = self.builder.build(ctx)

        assert "# Recent Conversation" in prompt
        assert "User asked about invoice #100." in prompt

    def test_conversation_summary_excluded_when_empty(self):
        """Conversation history section is omitted when conversation_summary is empty."""
        ctx = PromptContext(conversation_summary="")
        prompt = self.builder.build(ctx)

        assert "# Recent Conversation" not in prompt

    def test_user_roles_none_displayed(self):
        """When user_roles is empty, 'none' is shown."""
        ctx = PromptContext(user_name="NoRolesUser", user_roles=[])
        prompt = self.builder.build(ctx)

        assert "Roles: none" in prompt

    def test_tool_risk_defaults_to_read(self):
        """When risk_level is missing from a tool summary, it defaults to 'read'."""
        ctx = PromptContext(
            tool_summaries=[
                {"name": "simple-tool", "description": "A tool without risk_level"},
            ],
        )
        prompt = self.builder.build(ctx)

        assert "**simple-tool** (read):" in prompt

    def test_sections_separated_by_double_newline(self):
        """All sections are separated by double newlines."""
        ctx = PromptContext()
        prompt = self.builder.build(ctx)

        sections = prompt.split("\n\n")
        # Must have at least identity, user, tools, widget, guidelines content
        assert len(sections) >= 5
