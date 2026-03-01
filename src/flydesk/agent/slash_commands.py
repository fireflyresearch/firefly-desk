# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Slash commands -- diagnostic and utility commands handled directly in chat.

Slash commands are prefixed with ``/`` and are intercepted before reaching the
LLM.  They return informational output about the agent's context, memory,
configuration, and operational status.
"""

from __future__ import annotations

import logging
import textwrap
from typing import TYPE_CHECKING, Any

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from flydesk.agent.context import ContextEnricher
    from flydesk.agent.genai_bridge import DeskAgentFactory
    from flydesk.auth.models import UserSession
    from flydesk.conversation.repository import ConversationRepository
    from flydesk.llm.repository import LLMProviderRepository
    from flydesk.memory.repository import MemoryRepository
    from flydesk.settings.repository import SettingsRepository

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_slash_command(message: str) -> bool:
    """Return True if the message looks like a slash command."""
    return message.startswith("/") and not message.startswith("//")


async def handle_slash_command(
    message: str,
    *,
    conversation_id: str,
    session: UserSession | None = None,
    conversation_repo: ConversationRepository | None = None,
    context_enricher: ContextEnricher | None = None,
    agent_factory: DeskAgentFactory | None = None,
    llm_repo: LLMProviderRepository | None = None,
    settings_repo: SettingsRepository | None = None,
    memory_repo: MemoryRepository | None = None,
) -> str:
    """Dispatch a slash command and return a markdown response string."""
    parts = message.strip().split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    handler = _COMMANDS.get(cmd)
    if handler is None:
        return _help_text()

    try:
        return await handler(
            arg=arg,
            conversation_id=conversation_id,
            session=session,
            conversation_repo=conversation_repo,
            context_enricher=context_enricher,
            agent_factory=agent_factory,
            llm_repo=llm_repo,
            settings_repo=settings_repo,
            memory_repo=memory_repo,
        )
    except Exception as exc:
        _logger.error("Slash command %s failed: %s", cmd, exc, exc_info=True)
        return f"**Error running `{cmd}`:** {exc}"


# ---------------------------------------------------------------------------
# Individual command implementations
# ---------------------------------------------------------------------------


async def _cmd_help(**_: Any) -> str:
    return _help_text()


async def _cmd_status(
    *,
    llm_repo: LLMProviderRepository | None = None,
    agent_factory: DeskAgentFactory | None = None,
    **_: Any,
) -> str:
    """Show LLM provider status and agent configuration."""
    lines = ["## Agent Status\n"]

    # LLM provider
    if llm_repo:
        try:
            provider = await llm_repo.get_default_provider()
            if provider:
                lines.append(f"**LLM Provider:** {provider.name} ({provider.provider_type.value})")
                lines.append(f"**Model:** `{provider.default_model}`")
                lines.append(f"**API Key:** {'configured' if provider.api_key else 'missing'}")
                if provider.models:
                    model_names = [m.id for m in provider.models]
                    lines.append(f"**Available Models:** {', '.join(f'`{m}`' for m in model_names)}")
            else:
                lines.append("**LLM Provider:** not configured")
        except Exception as exc:
            lines.append(f"**LLM Provider:** error — {exc}")
    else:
        lines.append("**LLM Provider:** repository not available")

    # Fallback models
    if agent_factory:
        try:
            fallbacks = await agent_factory.get_fallback_model_strings()
            if fallbacks:
                lines.append(f"**Fallback Models:** {', '.join(f'`{m}`' for m in fallbacks)}")
            else:
                lines.append("**Fallback Models:** none configured")
        except Exception:
            _logger.debug("Failed to retrieve fallback models", exc_info=True)

    return "\n".join(lines)


async def _cmd_context(
    *,
    arg: str = "",
    conversation_id: str,
    session: UserSession | None = None,
    context_enricher: ContextEnricher | None = None,
    agent_factory: DeskAgentFactory | None = None,
    memory_repo: Any | None = None,
    **_: Any,
) -> str:
    """Run context enrichment for a query and show what the agent would see."""
    query = arg.strip()
    if not query:
        return (
            "**Usage:** `/context <query>`\n\n"
            "Run context enrichment for a query and show what the agent would see.\n\n"
            "**Example:** `/context how do I reset a password`"
        )

    if context_enricher is None:
        return "Context enricher not available."

    from flydesk.agent.context import EnrichedContext

    user_id = session.user_id if session else None
    enriched: EnrichedContext = await context_enricher.enrich(query, user_id=user_id)

    lines = [f"## Context Enrichment for: *{query}*\n"]

    # Entities
    lines.append(f"### Knowledge Graph Entities ({len(enriched.relevant_entities)})")
    if enriched.relevant_entities:
        for e in enriched.relevant_entities:
            lines.append(f"- **{e.name}** ({e.entity_type})")
    else:
        lines.append("*No matching entities found.*")

    # Knowledge snippets
    lines.append(f"\n### RAG Knowledge Snippets ({len(enriched.knowledge_snippets)})")
    if enriched.knowledge_snippets:
        for s in enriched.knowledge_snippets:
            title = getattr(s, "document_title", "untitled")
            content = getattr(s.chunk, "content", str(s))[:200]
            score = getattr(s, "score", None)
            score_str = f" (score: {score:.2f})" if score is not None else ""
            lines.append(f"- **[{title}]**{score_str}: {content}...")
    else:
        lines.append("*No knowledge snippets retrieved.*")

    # Processes
    lines.append(f"\n### Business Processes ({len(enriched.relevant_processes)})")
    if enriched.relevant_processes:
        for p in enriched.relevant_processes:
            name = getattr(p, "name", str(p))
            lines.append(f"- {name}")
    else:
        lines.append("*No matching processes.*")

    # User memories
    lines.append(f"\n### User Memories ({len(enriched.user_memories)})")
    if enriched.user_memories:
        for m in enriched.user_memories:
            content = getattr(m, "content", str(m))[:150]
            category = getattr(m, "category", "general")
            lines.append(f"- `{category}`: {content}")
    else:
        lines.append("*No matching user memories.*")

    # Memory usage stats
    lines.append("\n### Memory Usage")
    if agent_factory and hasattr(agent_factory, "_memory_manager"):
        mm = agent_factory._memory_manager
        if mm is not None:
            conv_mem = getattr(mm, "_conversation", None)
            if conv_mem:
                max_tokens = getattr(conv_mem, "_max_tokens", "unknown")
                threshold = getattr(conv_mem, "_summarize_threshold", "unknown")
                turns = getattr(conv_mem, "_turns", {})
                conv_turns = turns.get(conversation_id, [])
                summary = getattr(conv_mem, "_summaries", {}).get(conversation_id)

                # Estimate current token usage
                turn_chars = sum(
                    len(str(t)) for t in conv_turns
                )
                est_tokens = turn_chars // 4

                lines.append(f"- **Max Tokens:** {max_tokens:,}")
                lines.append(f"- **Current Tokens (est.):** ~{est_tokens:,}")
                if isinstance(max_tokens, int) and max_tokens > 0:
                    pct = round(est_tokens / max_tokens * 100, 1)
                    lines.append(f"- **Usage:** {pct}%")
                lines.append(f"- **Compaction Threshold:** {threshold}")
                lines.append(f"- **In-Memory Turns:** {len(conv_turns)}")
                lines.append(f"- **Summary:** {'yes' if summary else 'none'}")
            else:
                lines.append("*Conversation memory not configured.*")
        else:
            lines.append("*Memory manager not configured.*")
    else:
        lines.append("*Memory manager not available.*")

    # User memory count
    if memory_repo and user_id:
        try:
            all_memories = await memory_repo.list_for_user(user_id)
            lines.append(f"\n### Saved User Memories: **{len(all_memories)}**")
        except Exception:
            _logger.debug("Failed to list user memories", exc_info=True)

    return "\n".join(lines)


async def _cmd_memory(
    *,
    conversation_id: str,
    session: UserSession | None = None,
    conversation_repo: ConversationRepository | None = None,
    agent_factory: DeskAgentFactory | None = None,
    **_: Any,
) -> str:
    """Show conversation memory and history for the current conversation."""
    lines = ["## Conversation Memory\n"]
    user_id = session.user_id if session else "anonymous"

    # Conversation messages from DB
    if conversation_repo:
        try:
            messages = await conversation_repo.get_messages(
                conversation_id, user_id, limit=50,
            )
            lines.append(f"### Message History ({len(messages)} messages)")
            if messages:
                total_chars = sum(len(m.content) for m in messages)
                est_tokens = total_chars // 4  # rough estimate
                lines.append(f"**Total Characters:** {total_chars:,}")
                lines.append(f"**Estimated Tokens:** ~{est_tokens:,}")
                lines.append(f"**Oldest:** {messages[0].created_at}")
                lines.append(f"**Newest:** {messages[-1].created_at}")
                lines.append("")
                # Show last 5 messages as summary
                lines.append("**Last 5 messages:**")
                for msg in messages[-5:]:
                    role = msg.role.value.upper()
                    content_preview = msg.content[:120].replace("\n", " ")
                    if len(msg.content) > 120:
                        content_preview += "..."
                    lines.append(f"- `{role}`: {content_preview}")
            else:
                lines.append("*No messages in this conversation.*")
        except Exception as exc:
            lines.append(f"**Error loading messages:** {exc}")
    else:
        lines.append("*Conversation repository not available.*")

    # GenAI memory manager info
    if agent_factory and hasattr(agent_factory, "_memory_manager"):
        mm = agent_factory._memory_manager
        if mm is not None:
            lines.append("\n### GenAI Memory Manager")
            conv_mem = getattr(mm, "_conversation", None)
            if conv_mem:
                lines.append(f"**Max Tokens:** {getattr(conv_mem, '_max_tokens', 'unknown'):,}")
                lines.append(f"**Summarize Threshold:** {getattr(conv_mem, '_summarize_threshold', 'unknown')}")
                # Check if there are turns stored
                turns = getattr(conv_mem, "_turns", {})
                conv_turns = turns.get(conversation_id, [])
                lines.append(f"**In-Memory Turns:** {len(conv_turns)}")
                summary = getattr(conv_mem, "_summaries", {}).get(conversation_id)
                if summary:
                    lines.append(f"**Summary:** {summary[:200]}...")
                else:
                    lines.append("**Summary:** none (not yet compacted)")
            working_mem = getattr(mm, "_working", None)
            if working_mem:
                try:
                    keys = list(working_mem.keys())
                    lines.append(f"\n**Working Memory Keys:** {len(keys)}")
                    for k in keys[:10]:
                        v = working_mem.get(k)
                        lines.append(f"- `{k}` = {str(v)[:100]}")
                except Exception:
                    _logger.debug("Failed to inspect working memory", exc_info=True)
        else:
            lines.append("\n### GenAI Memory Manager\n*Not configured.*")

    return "\n".join(lines)


async def _cmd_config(
    *,
    session: UserSession | None = None,
    settings_repo: SettingsRepository | None = None,
    llm_repo: LLMProviderRepository | None = None,
    **_: Any,
) -> str:
    """Show agent configuration and settings."""
    lines = ["## Agent Configuration\n"]

    # User info
    if session:
        lines.append("### Current User")
        lines.append(f"- **ID:** {session.user_id}")
        lines.append(f"- **Name:** {getattr(session, 'display_name', 'unknown')}")
        lines.append(f"- **Roles:** {', '.join(getattr(session, 'roles', []))}")
        lines.append(f"- **Permissions:** {', '.join(getattr(session, 'permissions', []))}")

    # LLM providers
    if llm_repo:
        try:
            providers = await llm_repo.list_providers()
            lines.append(f"\n### LLM Providers ({len(providers)})")
            for p in providers:
                default_marker = " **(default)**" if p.is_default else ""
                active = "active" if p.is_active else "inactive"
                lines.append(
                    f"- `{p.name}` — {p.provider_type.value}, "
                    f"model: `{p.default_model}`, {active}{default_marker}"
                )
        except Exception as exc:
            lines.append(f"\n**Error listing providers:** {exc}")

    return "\n".join(lines)


async def _cmd_prompt(
    *,
    arg: str = "",
    conversation_id: str,
    session: UserSession | None = None,
    context_enricher: ContextEnricher | None = None,
    **_: Any,
) -> str:
    """Show a preview of the system prompt sections (without the full prompt)."""
    query = arg.strip() or "Hello"

    lines = ["## System Prompt Preview\n"]
    lines.append(
        "*This shows the context sections that would be injected into the system "
        "prompt. The actual prompt template is not shown for brevity.*\n"
    )

    if context_enricher is None:
        lines.append("*Context enricher not available — cannot preview.*")
        return "\n".join(lines)

    enriched = await context_enricher.enrich(query)

    # Knowledge context
    entity_count = len(enriched.relevant_entities)
    snippet_count = len(enriched.knowledge_snippets)
    process_count = len(enriched.relevant_processes)

    lines.append("### Injected Context Sizes")
    lines.append(f"- **Entities:** {entity_count} items")
    lines.append(f"- **Knowledge Snippets:** {snippet_count} items")
    lines.append(f"- **Processes:** {process_count} items")

    # Estimate total context tokens
    total_chars = 0
    for e in enriched.relevant_entities:
        total_chars += len(e.name) + len(e.entity_type) + 10
    for s in enriched.knowledge_snippets:
        total_chars += len(getattr(s.chunk, "content", ""))
    est_tokens = total_chars // 4
    lines.append(f"- **Estimated Context Tokens:** ~{est_tokens:,}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Help text and registry
# ---------------------------------------------------------------------------


def _help_text() -> str:
    return textwrap.dedent("""\
        ## Slash Commands

        | Command | Description |
        |---------|-------------|
        | `/help` | Show this help message |
        | `/status` | LLM provider status, model, fallback info |
        | `/context [query]` | Run context enrichment and show retrieved entities, knowledge, processes |
        | `/memory` | Show conversation memory, token counts, compaction status |
        | `/config` | Show agent configuration, user info, LLM providers |
        | `/prompt [query]` | Preview system prompt context sections |

        *Slash commands are processed locally and do not call the LLM.*
    """)


_COMMANDS: dict[str, Any] = {
    "/help": _cmd_help,
    "/status": _cmd_status,
    "/context": _cmd_context,
    "/memory": _cmd_memory,
    "/config": _cmd_config,
    "/prompt": _cmd_prompt,
}
