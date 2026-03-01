# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for AgentProfile, AgentCustomizationService, and identity_custom template."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from flydesk.agent.customization import AgentCustomizationService, AgentProfile
from flydesk.agent.prompt import PromptContext, SystemPromptBuilder
from flydesk.prompts.registry import register_desk_prompts
from flydesk.settings.models import AgentSettings


# ---------------------------------------------------------------------------
# AgentProfile model tests
# ---------------------------------------------------------------------------


class TestAgentProfile:
    """Tests for the AgentProfile Pydantic model."""

    def test_defaults(self):
        profile = AgentProfile()
        assert profile.name == "Ember"
        assert profile.display_name == "Ember"
        assert profile.avatar_url == ""
        assert profile.personality == "warm, professional, knowledgeable"
        assert profile.tone == "friendly yet precise"
        assert "{name}" in profile.greeting
        assert profile.behavior_rules == []
        assert profile.custom_instructions == ""
        assert profile.language == "en"

    def test_custom_values(self):
        profile = AgentProfile(
            name="Atlas",
            display_name="Atlas Bot",
            avatar_url="https://cdn.example.com/atlas.png",
            personality="formal, authoritative",
            tone="strict and concise",
            greeting="Welcome. I am Atlas.",
            behavior_rules=["Never skip confirmation steps"],
            custom_instructions="Focus on compliance queries.",
            language="es",
        )
        assert profile.name == "Atlas"
        assert profile.display_name == "Atlas Bot"
        assert profile.avatar_url == "https://cdn.example.com/atlas.png"
        assert profile.personality == "formal, authoritative"
        assert profile.tone == "strict and concise"
        assert profile.greeting == "Welcome. I am Atlas."
        assert profile.behavior_rules == ["Never skip confirmation steps"]
        assert profile.custom_instructions == "Focus on compliance queries."
        assert profile.language == "es"

    def test_serialization_roundtrip(self):
        profile = AgentProfile(
            name="Test",
            behavior_rules=["Rule 1", "Rule 2"],
        )
        data = profile.model_dump()
        restored = AgentProfile(**data)
        assert restored == profile


# ---------------------------------------------------------------------------
# AgentCustomizationService tests
# ---------------------------------------------------------------------------


class TestAgentCustomizationService:
    """Tests for the AgentCustomizationService."""

    @pytest.fixture
    def mock_settings_repo(self) -> AsyncMock:
        repo = AsyncMock()
        repo.get_agent_settings = AsyncMock(return_value=AgentSettings())
        repo.set_agent_settings = AsyncMock(return_value=None)
        return repo

    @pytest.fixture
    def service(self, mock_settings_repo) -> AgentCustomizationService:
        return AgentCustomizationService(mock_settings_repo)

    async def test_get_profile_returns_defaults(self, service):
        """get_profile returns Ember defaults when no custom settings exist."""
        profile = await service.get_profile()
        assert profile.name == "Ember"
        assert profile.personality == "warm, professional, knowledgeable"

    async def test_get_profile_loads_from_db(self, service, mock_settings_repo):
        """get_profile loads custom settings from the DB."""
        mock_settings_repo.get_agent_settings.return_value = AgentSettings(
            name="Atlas",
            display_name="Atlas Bot",
            personality="formal, authoritative",
            tone="corporate",
        )
        profile = await service.get_profile()
        assert profile.name == "Atlas"
        assert profile.display_name == "Atlas Bot"
        assert profile.personality == "formal, authoritative"
        assert profile.tone == "corporate"

    async def test_get_profile_caches_result(self, service, mock_settings_repo):
        """get_profile caches the result and does not re-read DB on second call."""
        await service.get_profile()
        await service.get_profile()
        # Should only have been called once due to caching
        assert mock_settings_repo.get_agent_settings.await_count == 1

    async def test_get_profile_falls_back_on_error(self, service, mock_settings_repo):
        """get_profile falls back to Ember defaults when DB read fails."""
        mock_settings_repo.get_agent_settings.side_effect = RuntimeError("DB down")
        profile = await service.get_profile()
        assert profile.name == "Ember"
        assert profile.personality == "warm, professional, knowledgeable"

    async def test_update_profile_persists_and_updates_cache(
        self, service, mock_settings_repo
    ):
        """update_profile persists to DB and updates the cached profile."""
        new_profile = AgentProfile(
            name="Nova",
            display_name="Nova AI",
            personality="energetic, creative",
            tone="casual",
        )
        result = await service.update_profile(new_profile)
        assert result.name == "Nova"
        mock_settings_repo.set_agent_settings.assert_awaited_once()

        # Subsequent get_profile should return cached value
        cached = await service.get_profile()
        assert cached.name == "Nova"
        # DB should not have been queried again
        assert mock_settings_repo.get_agent_settings.await_count == 0

    async def test_invalidate_cache(self, service, mock_settings_repo):
        """invalidate_cache forces re-read from DB on next get_profile."""
        await service.get_profile()
        service.invalidate_cache()
        await service.get_profile()
        assert mock_settings_repo.get_agent_settings.await_count == 2

    async def test_update_profile_converts_to_agent_settings(
        self, service, mock_settings_repo
    ):
        """update_profile should convert AgentProfile to AgentSettings for storage."""
        profile = AgentProfile(
            name="Bolt",
            behavior_rules=["Always confirm", "Log actions"],
            custom_instructions="Prioritize speed.",
        )
        await service.update_profile(profile)

        call_args = mock_settings_repo.set_agent_settings.call_args[0][0]
        assert isinstance(call_args, AgentSettings)
        assert call_args.name == "Bolt"
        assert call_args.behavior_rules == ["Always confirm", "Log actions"]
        assert call_args.custom_instructions == "Prioritize speed."


# ---------------------------------------------------------------------------
# Identity custom template rendering tests
# ---------------------------------------------------------------------------


class TestIdentityCustomTemplate:
    """Tests that the identity_custom.j2 template renders correctly."""

    def setup_method(self):
        self.registry = register_desk_prompts()
        self.builder = SystemPromptBuilder(self.registry)

    def test_custom_template_renders_personality(self):
        """The custom template should include personality text."""
        ctx = PromptContext(
            agent_name="Atlas",
            personality="formal, authoritative",
            tone="corporate",
        )
        prompt = self.builder.build(ctx)
        assert "formal, authoritative" in prompt
        assert "corporate" in prompt
        assert "Atlas" in prompt

    def test_custom_template_renders_behavior_rules(self):
        """The custom template should list behavior rules."""
        ctx = PromptContext(
            agent_name="Atlas",
            personality="helpful",
            behavior_rules=["Always confirm before executing actions", "Log every tool call"],
        )
        prompt = self.builder.build(ctx)
        assert "Always confirm before executing actions" in prompt
        assert "Log every tool call" in prompt
        assert "## Behavior Rules" in prompt

    def test_custom_template_omits_behavior_rules_when_empty(self):
        """The custom template should omit behavior rules section when empty."""
        ctx = PromptContext(
            agent_name="Atlas",
            personality="helpful",
            behavior_rules=[],
        )
        prompt = self.builder.build(ctx)
        assert "## Behavior Rules" not in prompt

    def test_custom_template_renders_custom_instructions(self):
        """The custom template should include custom instructions."""
        ctx = PromptContext(
            agent_name="Atlas",
            personality="helpful",
            custom_instructions="Focus on billing queries only.",
        )
        prompt = self.builder.build(ctx)
        assert "Focus on billing queries only." in prompt
        assert "## Additional Instructions" in prompt

    def test_custom_template_omits_custom_instructions_when_empty(self):
        """The custom template should omit the additional instructions section when empty."""
        ctx = PromptContext(
            agent_name="Atlas",
            personality="helpful",
            custom_instructions="",
        )
        prompt = self.builder.build(ctx)
        assert "## Additional Instructions" not in prompt

    def test_custom_template_includes_company(self):
        """The custom template should include company name when provided."""
        ctx = PromptContext(
            agent_name="Atlas",
            company_name="Acme Corp",
            personality="helpful",
        )
        prompt = self.builder.build(ctx)
        assert "Atlas for Acme Corp" in prompt

    def test_custom_template_non_english_language(self):
        """The custom template should include language instruction for non-English."""
        ctx = PromptContext(
            agent_name="Atlas",
            personality="helpful",
            language="es",
        )
        prompt = self.builder.build(ctx)
        assert '"es"' in prompt

    def test_custom_template_english_language_default(self):
        """The custom template should use 'respond in same language' for English."""
        ctx = PromptContext(
            agent_name="Atlas",
            personality="helpful",
            language="en",
        )
        prompt = self.builder.build(ctx)
        assert "respond in the same language as the user" in prompt

    def test_custom_template_includes_knowledge_and_honesty(self):
        """The custom template should always include knowledge and honesty section."""
        ctx = PromptContext(
            agent_name="Atlas",
            personality="helpful",
        )
        prompt = self.builder.build(ctx)
        assert "## Knowledge and Honesty" in prompt
        assert "backoffice operations assistant" in prompt

    def test_ember_defaults_when_no_customization(self):
        """When no customization fields are set, Ember defaults are applied."""
        ctx = PromptContext(agent_name="Ember")
        prompt = self.builder.build(ctx)
        assert "Ember" in prompt
        assert "warm, professional, knowledgeable" in prompt

    def test_non_ember_defaults_when_no_customization(self):
        """Non-Ember agent with no customization still uses custom template with defaults."""
        ctx = PromptContext(agent_name="Custom Bot")
        prompt = self.builder.build(ctx)
        assert "Custom Bot" in prompt
        assert "warm, professional, knowledgeable" in prompt

    def test_ember_with_customization_uses_custom_template(self):
        """Ember with personality override should use the custom template."""
        ctx = PromptContext(
            agent_name="Ember",
            personality="cheerful and enthusiastic",
            tone="upbeat",
        )
        prompt = self.builder.build(ctx)
        assert "cheerful and enthusiastic" in prompt
        assert "upbeat" in prompt
        # Should NOT use the hardcoded Ember template text
        assert "steady, persistent glow of a firefly" not in prompt


# ---------------------------------------------------------------------------
# PromptContext new fields tests
# ---------------------------------------------------------------------------


class TestPromptContextCustomizationFields:
    """Tests for the new customization fields on PromptContext."""

    def test_defaults(self):
        ctx = PromptContext()
        assert ctx.personality == ""
        assert ctx.behavior_rules == []
        assert ctx.greeting == ""
        assert ctx.tone == ""
        assert ctx.custom_instructions == ""
        assert ctx.language == "en"

    def test_accepts_customization_fields(self):
        ctx = PromptContext(
            personality="formal",
            behavior_rules=["Rule 1"],
            greeting="Hello!",
            tone="corporate",
            custom_instructions="Extra instructions",
            language="fr",
        )
        assert ctx.personality == "formal"
        assert ctx.behavior_rules == ["Rule 1"]
        assert ctx.greeting == "Hello!"
        assert ctx.tone == "corporate"
        assert ctx.custom_instructions == "Extra instructions"
        assert ctx.language == "fr"


# ---------------------------------------------------------------------------
# DeskAgent integration with AgentCustomizationService tests
# ---------------------------------------------------------------------------


class TestDeskAgentCustomizationIntegration:
    """Tests for DeskAgent loading AgentProfile in _prepare_turn."""

    @pytest.fixture
    def mock_customization_service(self) -> AsyncMock:
        svc = AsyncMock(spec=AgentCustomizationService)
        svc.get_profile_for_user = AsyncMock(
            return_value=AgentProfile(
                name="Atlas",
                personality="formal, authoritative",
                tone="corporate",
                behavior_rules=["Always confirm before executing"],
                custom_instructions="Focus on compliance.",
                language="en",
            )
        )
        return svc

    @pytest.fixture
    def desk_agent(self, mock_customization_service):
        from flydesk.agent.context import ContextEnricher, EnrichedContext
        from flydesk.agent.desk_agent import DeskAgent
        from flydesk.audit.logger import AuditLogger
        from flydesk.tools.factory import ToolFactory
        from flydesk.widgets.parser import ParseResult, WidgetParser

        context_enricher = MagicMock(spec=ContextEnricher)
        context_enricher.enrich = AsyncMock(
            return_value=EnrichedContext(
                relevant_entities=[],
                knowledge_snippets=[],
                conversation_history=[],
            )
        )
        prompt_builder = MagicMock(spec=SystemPromptBuilder)
        prompt_builder.build = MagicMock(return_value="System prompt")
        tool_factory = MagicMock(spec=ToolFactory)
        widget_parser = MagicMock(spec=WidgetParser)
        widget_parser.parse = MagicMock(
            return_value=ParseResult(text_segments=["Hello"], widgets=[])
        )
        audit_logger = MagicMock(spec=AuditLogger)
        audit_logger.log = AsyncMock(return_value="audit-1")

        return DeskAgent(
            context_enricher=context_enricher,
            prompt_builder=prompt_builder,
            tool_factory=tool_factory,
            widget_parser=widget_parser,
            audit_logger=audit_logger,
            agent_name="Ember",
            customization_service=mock_customization_service,
        )

    @pytest.fixture
    def user_session(self):
        from datetime import datetime, timezone

        from flydesk.auth.models import UserSession

        return UserSession(
            user_id="user-42",
            email="alice@example.com",
            display_name="Alice",
            roles=["admin"],
            permissions=["*"],
            tenant_id="t-1",
            session_id="s-1",
            token_expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
            raw_claims={},
        )

    async def test_prepare_turn_loads_profile(
        self, desk_agent, mock_customization_service, user_session
    ):
        """_prepare_turn should call get_profile_for_user on the customization service."""
        await desk_agent.run("Hello", user_session, "conv-1")
        mock_customization_service.get_profile_for_user.assert_awaited_once_with("user-42")

    async def test_prepare_turn_passes_customization_to_prompt_context(
        self, desk_agent, mock_customization_service, user_session
    ):
        """_prepare_turn should pass profile fields to PromptContext."""
        await desk_agent.run("Hello", user_session, "conv-1")
        prompt_builder = desk_agent._prompt_builder
        call_ctx = prompt_builder.build.call_args[0][0]
        assert isinstance(call_ctx, PromptContext)
        assert call_ctx.agent_name == "Atlas"
        assert call_ctx.personality == "formal, authoritative"
        assert call_ctx.tone == "corporate"
        assert call_ctx.behavior_rules == ["Always confirm before executing"]
        assert call_ctx.custom_instructions == "Focus on compliance."

    async def test_prepare_turn_without_customization_service(self, user_session):
        """Without a customization service, _prepare_turn uses static agent_name."""
        from flydesk.agent.context import ContextEnricher, EnrichedContext
        from flydesk.agent.desk_agent import DeskAgent
        from flydesk.audit.logger import AuditLogger
        from flydesk.tools.factory import ToolFactory
        from flydesk.widgets.parser import ParseResult, WidgetParser

        context_enricher = MagicMock(spec=ContextEnricher)
        context_enricher.enrich = AsyncMock(
            return_value=EnrichedContext(
                relevant_entities=[],
                knowledge_snippets=[],
                conversation_history=[],
            )
        )
        prompt_builder = MagicMock(spec=SystemPromptBuilder)
        prompt_builder.build = MagicMock(return_value="System prompt")
        widget_parser = MagicMock(spec=WidgetParser)
        widget_parser.parse = MagicMock(
            return_value=ParseResult(text_segments=["Hello"], widgets=[])
        )
        audit_logger = MagicMock(spec=AuditLogger)
        audit_logger.log = AsyncMock(return_value="audit-1")

        agent = DeskAgent(
            context_enricher=context_enricher,
            prompt_builder=prompt_builder,
            tool_factory=MagicMock(spec=ToolFactory),
            widget_parser=widget_parser,
            audit_logger=audit_logger,
            agent_name="Ember",
        )
        await agent.run("Hello", user_session, "conv-1")
        call_ctx = prompt_builder.build.call_args[0][0]
        assert call_ctx.agent_name == "Ember"
        assert call_ctx.personality == ""
        assert call_ctx.tone == ""

    async def test_prepare_turn_handles_customization_service_error(
        self, user_session
    ):
        """When customization service errors, _prepare_turn uses static defaults."""
        from flydesk.agent.context import ContextEnricher, EnrichedContext
        from flydesk.agent.desk_agent import DeskAgent
        from flydesk.audit.logger import AuditLogger
        from flydesk.tools.factory import ToolFactory
        from flydesk.widgets.parser import ParseResult, WidgetParser

        failing_svc = AsyncMock(spec=AgentCustomizationService)
        failing_svc.get_profile_for_user = AsyncMock(side_effect=RuntimeError("DB error"))

        context_enricher = MagicMock(spec=ContextEnricher)
        context_enricher.enrich = AsyncMock(
            return_value=EnrichedContext(
                relevant_entities=[],
                knowledge_snippets=[],
                conversation_history=[],
            )
        )
        prompt_builder = MagicMock(spec=SystemPromptBuilder)
        prompt_builder.build = MagicMock(return_value="System prompt")
        widget_parser = MagicMock(spec=WidgetParser)
        widget_parser.parse = MagicMock(
            return_value=ParseResult(text_segments=["Hello"], widgets=[])
        )
        audit_logger = MagicMock(spec=AuditLogger)
        audit_logger.log = AsyncMock(return_value="audit-1")

        agent = DeskAgent(
            context_enricher=context_enricher,
            prompt_builder=prompt_builder,
            tool_factory=MagicMock(spec=ToolFactory),
            widget_parser=widget_parser,
            audit_logger=audit_logger,
            agent_name="Ember",
            customization_service=failing_svc,
        )
        # Should not raise; falls back to static defaults
        await agent.run("Hello", user_session, "conv-1")
        call_ctx = prompt_builder.build.call_args[0][0]
        assert call_ctx.agent_name == "Ember"
        assert call_ctx.personality == ""
