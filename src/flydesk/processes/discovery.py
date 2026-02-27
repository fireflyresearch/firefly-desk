# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Process Discovery LLM Analysis Engine.

Uses fireflyframework-genai (via ``DeskAgentFactory``) to analyze enterprise
catalog systems, knowledge graph entities, and knowledge base documents to
automatically discover business processes.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, Field

from flydesk.audit.logger import AuditLogger
from flydesk.audit.models import AuditEvent, AuditEventType
from flydesk.jobs.handlers import ProgressCallback
from flydesk.processes.models import (
    BusinessProcess,
    ProcessDependency,
    ProcessSource,
    ProcessStatus,
    ProcessStep,
)

if TYPE_CHECKING:
    from flydesk.agent.genai_bridge import DeskAgentFactory
    from flydesk.catalog.repository import CatalogRepository
    from flydesk.jobs.models import Job
    from flydesk.jobs.runner import JobRunner
    from flydesk.knowledge.graph import KnowledgeGraph
    from flydesk.processes.repository import ProcessRepository

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic models for parsing the LLM's structured JSON response
# ---------------------------------------------------------------------------

_PROMPTS_DIR = Path(__file__).parent / "prompts"


class DiscoveredStep(BaseModel):
    """A single step from the LLM discovery response."""

    id: str
    name: str
    description: str = ""
    step_type: str = "action"
    system_id: str | None = None
    endpoint_id: str | None = None
    order: int = 0
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)


class DiscoveredDependency(BaseModel):
    """A dependency edge from the LLM discovery response."""

    source_step_id: str
    target_step_id: str
    condition: str | None = None


class DiscoveredProcess(BaseModel):
    """A single process from the LLM discovery response."""

    name: str
    description: str = ""
    category: str = ""
    confidence: float = 0.0
    tags: list[str] = Field(default_factory=list)
    steps: list[DiscoveredStep] = Field(default_factory=list)
    dependencies: list[DiscoveredDependency] = Field(default_factory=list)


class DiscoveryResult(BaseModel):
    """Top-level LLM response schema for process discovery."""

    processes: list[DiscoveredProcess] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Context data containers
# ---------------------------------------------------------------------------


@dataclass
class SystemContext:
    """Flattened system + endpoints for template rendering."""

    id: str
    name: str
    description: str
    base_url: str
    status: str
    tags: list[str] = field(default_factory=list)
    endpoints: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DiscoveryContext:
    """All gathered context fed into the LLM prompt."""

    systems: list[SystemContext] = field(default_factory=list)
    entities: list[dict[str, Any]] = field(default_factory=list)
    relations: list[dict[str, Any]] = field(default_factory=list)
    documents: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_system_only(doc: Any, system_ws_id: str) -> bool:
    """Return True if *doc* belongs exclusively to the system workspace."""
    ws_ids: list[str] = getattr(doc, "workspace_ids", []) or []
    return ws_ids == [system_ws_id]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class ProcessDiscoveryEngine:
    """Discovers business processes by analyzing enterprise context with an LLM.

    Orchestrates the full discovery flow:
    1. Gather context from catalog, knowledge graph, and knowledge base
    2. Build structured prompts from Jinja2 templates
    3. Call an LLM via ``DeskAgentFactory`` (fireflyframework-genai)
    4. Parse the structured JSON response into ``BusinessProcess`` models
    5. Merge with existing processes (preserving user-verified/modified ones)
    6. Persist via ``ProcessRepository``
    """

    def __init__(
        self,
        agent_factory: DeskAgentFactory,
        process_repo: ProcessRepository,
        catalog_repo: CatalogRepository,
        knowledge_graph: KnowledgeGraph,
        *,
        audit_logger: AuditLogger | None = None,
        prompts_dir: Path | None = None,
    ) -> None:
        self._agent_factory = agent_factory
        self._process_repo = process_repo
        self._catalog_repo = catalog_repo
        self._knowledge_graph = knowledge_graph
        self._audit_logger = audit_logger

        templates_path = prompts_dir or _PROMPTS_DIR
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(templates_path)),
            autoescape=False,
        )

    @staticmethod
    def _extract_usage(result: object, agent: object) -> dict[str, Any]:
        """Extract token usage and cost from an agent.run() result."""
        try:
            usage_fn = getattr(result, "usage", None)
            usage = usage_fn() if callable(usage_fn) else None
            if usage is None:
                return {}

            input_tokens = getattr(usage, "input_tokens", 0) or 0
            output_tokens = getattr(usage, "output_tokens", 0) or 0
            total_tokens = getattr(usage, "total_tokens", 0) or (input_tokens + output_tokens)
            model_name = getattr(agent, "_model_identifier", "unknown")

            cost_usd = 0.0
            try:
                from fireflyframework_genai.config import get_config
                from fireflyframework_genai.observability.cost import get_cost_calculator

                cfg = get_config()
                calculator = get_cost_calculator(cfg.cost_calculator)
                cost_usd = calculator.estimate(model_name, input_tokens, output_tokens)
            except Exception:
                logger.debug("Cost estimation not available.", exc_info=True)

            return {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "cost_usd": round(cost_usd, 6),
                "model": model_name,
            }
        except Exception:
            logger.debug("Failed to extract discovery usage.", exc_info=True)
            return {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def discover(
        self,
        trigger: str,
        job_runner: JobRunner,
        *,
        workspace_ids: list[str] | None = None,
        document_types: list[str] | None = None,
    ) -> Job:
        """Submit a process discovery job to the background job runner.

        Parameters:
            trigger: Human-readable trigger description (e.g. "New CRM system added").
            job_runner: The ``JobRunner`` instance to submit the job to.
            workspace_ids: Optional list of workspace IDs to scope discovery to.
            document_types: Optional list of document types to include.

        Returns:
            The created ``Job`` domain object for tracking.
        """
        payload: dict[str, Any] = {"trigger": trigger}
        if workspace_ids:
            payload["workspace_ids"] = workspace_ids
        if document_types:
            payload["document_types"] = document_types
        return await job_runner.submit("process_discovery", payload)

    # ------------------------------------------------------------------
    # Analysis (called by ProcessDiscoveryHandler)
    # ------------------------------------------------------------------

    async def _analyze(
        self,
        job_id: str,
        payload: dict,
        on_progress: ProgressCallback,
    ) -> dict:
        """Run the full process discovery analysis pipeline.

        This method is invoked by ``ProcessDiscoveryHandler.execute()``.

        Returns a summary dict to be stored as the job result.
        """
        trigger = payload.get("trigger", "")
        workspace_ids = payload.get("workspace_ids") or []
        document_types = payload.get("document_types") or []
        await on_progress(5, "Scanning catalog systems, knowledge graph, and documents...")

        # 1. Gather context
        context = await self._gather_context(
            workspace_ids=workspace_ids,
            document_types=document_types,
            on_progress=on_progress,
        )
        # Build a descriptive summary of what was gathered
        total_endpoints = sum(len(s.endpoints) for s in context.systems)
        context_summary = (
            f"{len(context.systems)} systems, "
            f"{total_endpoints} endpoints, "
            f"{len(context.entities)} entities, "
            f"{len(context.relations)} relations, "
            f"{len(context.documents)} documents"
        )
        await on_progress(20, f"Context gathered: {context_summary}")

        # Warn if context is empty
        if not context.systems and not context.entities and not context.documents:
            await on_progress(100, "No context available — add systems, documents, or knowledge graph entities before running discovery")
            return {
                "status": "skipped",
                "reason": "no_context",
                "processes_discovered": 0,
            }

        # 2. Build prompt
        system_prompt = self._render_system_prompt(trigger)
        user_prompt = self._render_context_prompt(context)
        prompt_size = len(system_prompt) + len(user_prompt)
        await on_progress(
            25,
            f"Sending {prompt_size:,} characters of context to LLM for analysis...",
        )

        # 3. Call LLM (with progress feedback and retry)
        discovery_result, usage_data = await self._call_llm(
            system_prompt, user_prompt, on_progress,
        )
        if discovery_result is None:
            await on_progress(100, "No LLM provider configured — discovery skipped")
            return {
                "status": "skipped",
                "reason": "no_llm_configured",
                "processes_discovered": 0,
            }

        # Build a summary of discovered processes with names and confidence
        proc_count = len(discovery_result.processes)
        if proc_count > 0:
            proc_summaries = [
                f"{p.name} ({int(p.confidence * 100)}%)"
                for p in discovery_result.processes[:8]
            ]
            proc_list = ", ".join(proc_summaries)
            if proc_count > 8:
                proc_list += f", ... and {proc_count - 8} more"
            await on_progress(60, f"LLM identified {proc_count} processes: {proc_list}")
        else:
            await on_progress(60, "LLM analysis complete — no processes identified in the provided context")

        # 4. Convert to domain models
        discovered = self._to_business_processes(discovery_result)
        await on_progress(70, "Merging discovered processes with existing data...")

        # 5. Merge with existing
        stats = await self._merge_processes(discovered)
        merge_parts = []
        if stats["created"]:
            merge_parts.append(f"{stats['created']} new")
        if stats["updated"]:
            merge_parts.append(f"{stats['updated']} updated")
        if stats["skipped"]:
            merge_parts.append(f"{stats['skipped']} unchanged (verified)")
        merge_summary = ", ".join(merge_parts) if merge_parts else "no changes"
        await on_progress(95, f"Merge complete: {merge_summary}")

        if self._audit_logger and usage_data:
            try:
                await self._audit_logger.log(AuditEvent(
                    event_type=AuditEventType.DISCOVERY_RESPONSE,
                    user_id="system",
                    action="process_discovery",
                    detail={
                        "job_id": job_id,
                        **usage_data,
                    },
                ))
            except Exception:
                logger.debug("Failed to log discovery audit event.", exc_info=True)

        result = {
            "status": "completed",
            "trigger": trigger,
            "context_summary": context_summary,
            "processes_discovered": stats["discovered"],
            "processes_created": stats["created"],
            "processes_updated": stats["updated"],
            "processes_skipped": stats["skipped"],
            "input_tokens": usage_data.get("input_tokens", 0),
            "output_tokens": usage_data.get("output_tokens", 0),
            "cost_usd": usage_data.get("cost_usd", 0.0),
            "model": usage_data.get("model", "unknown"),
        }
        await on_progress(
            100,
            f"Discovery complete — {stats['discovered']} processes discovered, "
            f"{stats['created']} created, {stats['updated']} updated",
        )
        return result

    # ------------------------------------------------------------------
    # Context gathering
    # ------------------------------------------------------------------

    async def _gather_context(
        self,
        *,
        workspace_ids: list[str] | None = None,
        document_types: list[str] | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> DiscoveryContext:
        """Collect all available enterprise context for the LLM prompt."""
        ctx = DiscoveryContext()

        async def _progress(pct: int, msg: str) -> None:
            if on_progress:
                await on_progress(pct, msg)

        # Catalog systems + endpoints
        try:
            await _progress(6, "Scanning catalog for registered systems...")
            if workspace_ids:
                all_systems: list = []
                for ws_id in workspace_ids:
                    ws_systems, _ = await self._catalog_repo.list_systems(workspace_id=ws_id)
                    all_systems.extend(ws_systems)
                # Deduplicate by system ID
                seen_ids: set[str] = set()
                systems = []
                for sys in all_systems:
                    if sys.id not in seen_ids:
                        seen_ids.add(sys.id)
                        systems.append(sys)
            else:
                systems, _ = await self._catalog_repo.list_systems()

            for i, sys in enumerate(systems):
                await _progress(
                    7 + (i * 3 // max(len(systems), 1)),
                    f"Scanning system: {sys.name} ({len(systems) - i - 1} remaining)...",
                )
                endpoints = await self._catalog_repo.list_endpoints(sys.id)
                ep_dicts = [
                    {
                        "id": ep.id,
                        "name": ep.name,
                        "description": ep.description,
                        "method": str(ep.method),
                        "path": ep.path,
                        "when_to_use": ep.when_to_use,
                        "risk_level": str(ep.risk_level),
                    }
                    for ep in endpoints
                ]
                ctx.systems.append(
                    SystemContext(
                        id=sys.id,
                        name=sys.name,
                        description=sys.description,
                        base_url=sys.base_url,
                        status=str(sys.status),
                        tags=sys.tags,
                        endpoints=ep_dicts,
                    )
                )
            total_endpoints = sum(len(s.endpoints) for s in ctx.systems)
            if ctx.systems:
                await _progress(
                    10,
                    f"Found {len(ctx.systems)} systems with {total_endpoints} endpoints",
                )
        except Exception:
            logger.warning("Failed to gather catalog context.", exc_info=True)

        # Knowledge graph entities + relations
        try:
            await _progress(11, "Querying knowledge graph for entities and relations...")
            entities = await self._knowledge_graph.list_entities(limit=100)
            ctx.entities = [
                {
                    "name": e.name,
                    "entity_type": e.entity_type,
                    "confidence": e.confidence,
                    "properties": e.properties,
                }
                for e in entities
            ]
            # Gather relations for each entity (first-degree)
            seen_relations: set[tuple[str, str, str]] = set()
            for entity in entities:
                graph = await self._knowledge_graph.get_entity_neighborhood(entity.id, depth=1)
                for rel in graph.relations:
                    key = (rel.source_id, rel.target_id, rel.relation_type)
                    if key not in seen_relations:
                        seen_relations.add(key)
                        ctx.relations.append(
                            {
                                "source_id": rel.source_id,
                                "target_id": rel.target_id,
                                "relation_type": rel.relation_type,
                                "properties": rel.properties,
                            }
                        )
            if ctx.entities:
                await _progress(
                    14,
                    f"Found {len(ctx.entities)} entities and {len(ctx.relations)} relations in knowledge graph",
                )
        except Exception:
            logger.warning("Failed to gather knowledge graph context.", exc_info=True)

        # Knowledge base documents
        try:
            await _progress(15, "Gathering knowledge base documents...")
            # Skip the internal system workspace unless explicitly requested
            from flydesk.server import DEFAULT_WORKSPACE_ID as _SYSTEM_WS

            if workspace_ids:
                all_docs = []
                for ws_id in workspace_ids:
                    ws_docs = await self._catalog_repo.list_knowledge_documents(workspace_id=ws_id)
                    all_docs.extend(ws_docs)
                # Deduplicate by ID
                seen_doc_ids: set[str] = set()
                documents = []
                for doc in all_docs:
                    doc_id = getattr(doc, "id", None)
                    if doc_id and doc_id not in seen_doc_ids:
                        seen_doc_ids.add(doc_id)
                        documents.append(doc)
            else:
                documents = await self._catalog_repo.list_knowledge_documents()
                # Exclude documents that belong *only* to the system workspace
                documents = [
                    doc for doc in documents
                    if not _is_system_only(doc, _SYSTEM_WS)
                ]

            if document_types:
                type_set = set(document_types)
                documents = [
                    doc for doc in documents
                    if str(getattr(doc, "document_type", "other")) in type_set
                ]

            for i, doc in enumerate(documents):
                title = getattr(doc, "title", "Untitled")
                if len(documents) > 3 and i % max(len(documents) // 5, 1) == 0:
                    await _progress(
                        16 + (i * 3 // max(len(documents), 1)),
                        f"Processing document: {title} ({i + 1}/{len(documents)})...",
                    )

            ctx.documents = [
                {
                    "title": getattr(doc, "title", ""),
                    "document_type": str(getattr(doc, "document_type", "other")),
                    "tags": getattr(doc, "tags", []),
                    "content": getattr(doc, "content", ""),
                }
                for doc in documents
            ]
            if ctx.documents:
                await _progress(
                    19,
                    f"Loaded {len(ctx.documents)} documents from knowledge base",
                )
        except Exception:
            logger.warning("Failed to gather knowledge base context.", exc_info=True)

        return ctx

    # ------------------------------------------------------------------
    # Prompt rendering
    # ------------------------------------------------------------------

    def _render_system_prompt(self, trigger: str) -> str:
        """Render the system prompt template."""
        template = self._jinja_env.get_template("discovery_system.j2")
        return template.render(trigger=trigger)

    def _render_context_prompt(self, context: DiscoveryContext) -> str:
        """Render the context template with gathered data."""
        template = self._jinja_env.get_template("discovery_context.j2")
        return template.render(
            systems=context.systems,
            entities=context.entities,
            relations=context.relations,
            documents=context.documents,
        )

    # ------------------------------------------------------------------
    # LLM interaction
    # ------------------------------------------------------------------

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        on_progress: ProgressCallback,
    ) -> tuple[DiscoveryResult | None, dict[str, Any]]:
        """Call the LLM and parse the response into a ``DiscoveryResult``.

        Includes retry logic: if the first response fails to parse, a repair
        prompt is sent asking the LLM to return valid JSON.

        Returns a tuple of (result, usage_data). Result is ``None`` if no LLM
        provider is configured.
        """
        agent = await self._agent_factory.create_agent(
            system_prompt,
            model_settings_override={"max_tokens": 65536},
        )
        if agent is None:
            logger.warning("No LLM provider configured; process discovery skipped.")
            return None, {}

        await on_progress(30, "Waiting for LLM analysis (this may take 1-2 minutes)...")

        usage_data: dict[str, Any] = {}

        # First attempt
        try:
            result = await agent.run(user_prompt)
            usage_data = self._extract_usage(result, agent)
            output_text = str(result.output)
        except Exception as exc:
            logger.exception("LLM call failed during process discovery.")
            await on_progress(50, f"LLM call failed: {exc.__class__.__name__}: {exc}")
            return DiscoveryResult(processes=[]), usage_data

        logger.info(
            "Process discovery LLM response: %d chars (first 500: %s)",
            len(output_text),
            output_text[:500],
        )
        await on_progress(45, f"LLM responded with {len(output_text):,} characters, parsing...")

        parsed, parse_error = self._parse_llm_response(output_text)
        if parsed.processes:
            return parsed, usage_data

        # Parsing failed — attempt JSON repair with a follow-up prompt
        if parse_error:
            # Detect likely truncation
            is_truncation = (
                "unterminated" in parse_error.lower()
                or "unexpected end" in parse_error.lower()
            )
            if is_truncation:
                await on_progress(
                    48,
                    "LLM response was truncated (token limit). Attempting to repair JSON...",
                )
            else:
                await on_progress(
                    48,
                    f"JSON parse issue: {parse_error[:120]}. Attempting repair...",
                )
            logger.warning(
                "First parse failed (%s), attempting repair prompt. Raw response (first 1000): %s",
                parse_error,
                output_text[:1000],
            )

            repair_prompt = (
                "Your previous response could not be parsed as valid JSON. "
                f"Parse error: {parse_error}\n\n"
                "IMPORTANT: Your response was likely truncated because it was too long. "
                "Please respond with a SHORTER, more concise version that still captures "
                "all the key processes. Use brief descriptions (1-2 sentences max). "
                "Limit step descriptions to a single sentence.\n\n"
                "Respond with ONLY a valid JSON object matching the schema "
                "from the system prompt. Start with { and end with }. "
                "No markdown, no code fences, no explanatory text.\n\n"
                "Here is the beginning of your previous response for reference:\n"
                f"{output_text[:6000]}"
            )
            try:
                repair_result = await agent.run(repair_prompt)
                repair_usage = self._extract_usage(repair_result, agent)
                for key in ("input_tokens", "output_tokens", "total_tokens"):
                    usage_data[key] = usage_data.get(key, 0) + repair_usage.get(key, 0)
                if repair_usage.get("cost_usd"):
                    usage_data["cost_usd"] = round(
                        usage_data.get("cost_usd", 0) + repair_usage["cost_usd"], 6
                    )
                if repair_usage.get("model"):
                    usage_data["model"] = repair_usage["model"]
                repair_text = str(repair_result.output)
                logger.info(
                    "Repair response: %d chars (first 500: %s)",
                    len(repair_text),
                    repair_text[:500],
                )
                repaired, repair_error = self._parse_llm_response(repair_text)
                if repaired.processes:
                    await on_progress(55, f"Repair successful — {len(repaired.processes)} processes parsed")
                    return repaired, usage_data
                if repair_error:
                    await on_progress(55, f"Repair also failed: {repair_error[:120]}")
                    logger.warning("Repair parse also failed: %s", repair_error)
            except Exception:
                logger.exception("Repair LLM call failed.")
                await on_progress(55, "Repair attempt failed — LLM error")

        return parsed, usage_data

    @staticmethod
    def _extract_json_from_text(text: str) -> str:
        """Extract JSON from LLM text, handling code blocks and mixed content.

        Also handles truncated JSON (e.g. from token limit) by closing open
        strings, arrays, and objects to produce parseable JSON.
        """
        cleaned = text.strip()

        # Strip markdown code blocks (```json ... ``` or ``` ... ```)
        code_block = re.search(r'```(?:json)?\s*\n([\s\S]*?)\n```', cleaned)
        if code_block:
            cleaned = code_block.group(1).strip()
        elif cleaned.startswith("```"):
            first_nl = cleaned.find("\n")
            if first_nl > 0:
                cleaned = cleaned[first_nl + 1:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        # Locate the first { to start JSON extraction
        if not cleaned.startswith("{"):
            brace_start = cleaned.find("{")
            if brace_start >= 0:
                cleaned = cleaned[brace_start:]
            else:
                return cleaned.strip()

        # Walk the string tracking depth, string state, etc.
        depth = 0
        in_string = False
        escape_next = False
        end_idx = -1
        for i, ch in enumerate(cleaned):
            if escape_next:
                escape_next = False
                continue
            if ch == '\\' and in_string:
                escape_next = True
                continue
            if ch == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end_idx = i
                    break
            elif ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1

        if end_idx > 0:
            cleaned = cleaned[:end_idx + 1]
        elif depth > 0:
            # JSON was truncated — attempt to repair by closing open structures
            cleaned = ProcessDiscoveryEngine._repair_truncated_json(cleaned)

        return cleaned.strip()

    @staticmethod
    def _repair_truncated_json(text: str) -> str:
        """Attempt to repair truncated JSON by closing open strings and braces.

        Walks the text tracking the nesting stack (object vs array) and
        whether we're inside a string. At the end, closes everything that's
        still open so the result is (hopefully) parseable.
        """
        # Strip any trailing partial value (e.g. a string that was cut mid-word)
        # by backing up to the last structural character or complete value.
        stack: list[str] = []  # '{' or '['
        in_string = False
        escape_next = False
        last_good = 0  # index of last "safe" truncation point

        for i, ch in enumerate(text):
            if escape_next:
                escape_next = False
                continue
            if ch == '\\' and in_string:
                escape_next = True
                continue
            if ch == '"' and not escape_next:
                in_string = not in_string
                if not in_string:
                    last_good = i  # end of string
                continue
            if in_string:
                continue
            # Outside a string
            if ch == '{':
                stack.append('{')
                last_good = i
            elif ch == '[':
                stack.append('[')
                last_good = i
            elif ch == '}':
                if stack and stack[-1] == '{':
                    stack.pop()
                last_good = i
            elif ch == ']':
                if stack and stack[-1] == '[':
                    stack.pop()
                last_good = i
            elif ch in (',', ':'):
                last_good = i

        if not stack and not in_string:
            return text  # already balanced

        # Truncate to last known-good position + close open structures
        # If we're in a string, close it first
        result = text
        if in_string:
            # Back up to remove partial string content after last complete token
            # Find the opening quote of the current string
            last_quote = text.rfind('"', 0, len(text))
            if last_quote > 0:
                # Check what's before the quote to decide how to truncate
                before = text[:last_quote].rstrip()
                if before.endswith(':'):
                    # We're in a value string — close it with empty string
                    result = before + '""'
                elif before.endswith(','):
                    # Trailing comma before a new key — remove the comma
                    result = before[:-1]
                else:
                    result = text[:last_quote + 1] + '"'
            else:
                result = text + '"'

        # Remove any trailing comma
        result = result.rstrip()
        if result.endswith(','):
            result = result[:-1]

        # Re-scan to determine remaining open structures
        stack = []
        in_string = False
        escape_next = False
        for ch in result:
            if escape_next:
                escape_next = False
                continue
            if ch == '\\' and in_string:
                escape_next = True
                continue
            if ch == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                stack.append('{')
            elif ch == '[':
                stack.append('[')
            elif ch == '}':
                if stack and stack[-1] == '{':
                    stack.pop()
            elif ch == ']':
                if stack and stack[-1] == '[':
                    stack.pop()

        # Close remaining open structures in reverse order
        for opener in reversed(stack):
            if opener == '{':
                result += '}'
            elif opener == '[':
                result += ']'

        return result

    @staticmethod
    def _parse_llm_response(text: str) -> tuple[DiscoveryResult, str | None]:
        """Parse the LLM's text response as JSON into a ``DiscoveryResult``.

        Returns a tuple of (result, error_message). If parsing succeeds,
        error_message is None. If it fails, error_message describes the issue
        and result contains an empty process list.
        """
        if not text or not text.strip():
            return DiscoveryResult(processes=[]), "Empty LLM response"

        cleaned = ProcessDiscoveryEngine._extract_json_from_text(text)

        if not cleaned:
            return DiscoveryResult(processes=[]), "No JSON found in LLM response"

        # Try direct parse
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Try fixing common LLM JSON issues
            fixed = cleaned
            # Remove trailing commas before } or ]
            fixed = re.sub(r',\s*([}\]])', r'\1', fixed)
            # Remove JS-style comments
            fixed = re.sub(r'//[^\n]*', '', fixed)

            try:
                data = json.loads(fixed)
            except json.JSONDecodeError:
                error_msg = f"JSON parse error at position {e.pos}: {e.msg}"
                logger.warning(
                    "Failed to parse LLM response as JSON: %s. "
                    "First 500 chars: %s",
                    error_msg,
                    text[:500],
                )
                return DiscoveryResult(processes=[]), error_msg

        # Handle case where LLM returns a bare list instead of {processes: [...]}
        if isinstance(data, list):
            data = {"processes": data}

        try:
            result = DiscoveryResult.model_validate(data)
            return result, None
        except Exception as exc:
            error_msg = f"Schema validation failed: {exc}"
            logger.warning(
                "LLM JSON did not match DiscoveryResult schema: %s",
                error_msg,
            )
            return DiscoveryResult(processes=[]), error_msg

    # ------------------------------------------------------------------
    # Domain model conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _to_business_processes(result: DiscoveryResult) -> list[BusinessProcess]:
        """Convert parsed LLM output to ``BusinessProcess`` domain models.

        Step IDs from the LLM are namespaced with a short UUID prefix to
        guarantee global uniqueness across processes (the DB requires unique
        step IDs).
        """
        processes: list[BusinessProcess] = []
        for disc_proc in result.processes:
            process_id = str(uuid.uuid4())
            # Short prefix to namespace step IDs (first 8 chars of process UUID)
            prefix = process_id[:8]

            # Build a mapping from LLM step ID -> namespaced step ID
            step_id_map = {
                step.id: f"{prefix}-{step.id}" for step in disc_proc.steps
            }

            steps = [
                ProcessStep(
                    id=step_id_map[step.id],
                    name=step.name,
                    description=step.description,
                    step_type=step.step_type,
                    system_id=step.system_id,
                    endpoint_id=step.endpoint_id,
                    order=step.order,
                    inputs=step.inputs,
                    outputs=step.outputs,
                )
                for step in disc_proc.steps
            ]
            dependencies = [
                ProcessDependency(
                    source_step_id=step_id_map.get(dep.source_step_id, dep.source_step_id),
                    target_step_id=step_id_map.get(dep.target_step_id, dep.target_step_id),
                    condition=dep.condition,
                )
                for dep in disc_proc.dependencies
            ]
            processes.append(
                BusinessProcess(
                    id=process_id,
                    name=disc_proc.name,
                    description=disc_proc.description,
                    category=disc_proc.category,
                    steps=steps,
                    dependencies=dependencies,
                    source=ProcessSource.AUTO_DISCOVERED,
                    confidence=disc_proc.confidence,
                    status=ProcessStatus.DISCOVERED,
                    tags=disc_proc.tags,
                )
            )
        return processes

    # ------------------------------------------------------------------
    # Merge strategy
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize process name for fuzzy matching."""
        # Lowercase, strip extra whitespace, remove common suffixes
        name = name.lower().strip()
        name = re.sub(r'\s+', ' ', name)
        for suffix in (' process', ' workflow', ' procedure', ' flow'):
            if name.endswith(suffix):
                name = name[:-len(suffix)]
        return name

    async def _merge_processes(
        self,
        discovered: list[BusinessProcess],
    ) -> dict[str, int]:
        """Merge discovered processes with existing ones.

        Merge rules:
        - VERIFIED or MODIFIED processes are NEVER overwritten or deleted
        - Existing DISCOVERED processes with the same name get their confidence
          updated and steps refreshed
        - Brand new processes are created

        Returns a stats dict with counts.
        """
        stats = {"discovered": len(discovered), "created": 0, "updated": 0, "skipped": 0}

        existing = await self._process_repo.list(limit=500)
        existing_by_name: dict[str, BusinessProcess] = {
            self._normalize_name(p.name): p for p in existing
        }

        for proc in discovered:
            normalized = self._normalize_name(proc.name)
            existing_proc = existing_by_name.get(normalized)

            if existing_proc is None:
                # Brand new process -- create it
                await self._process_repo.create(proc)
                stats["created"] += 1
            elif existing_proc.status in (ProcessStatus.VERIFIED, ProcessStatus.MODIFIED):
                # User has verified or modified -- do not overwrite
                logger.debug(
                    "Skipping merge for '%s' (status=%s)",
                    existing_proc.name,
                    existing_proc.status,
                )
                stats["skipped"] += 1
            else:
                # Existing DISCOVERED or ARCHIVED process -- update it
                existing_proc.description = proc.description
                existing_proc.category = proc.category
                existing_proc.confidence = proc.confidence
                existing_proc.steps = proc.steps
                existing_proc.dependencies = proc.dependencies
                existing_proc.tags = proc.tags
                existing_proc.source = ProcessSource.AUTO_DISCOVERED
                existing_proc.status = ProcessStatus.DISCOVERED
                await self._process_repo.update(existing_proc)
                stats["updated"] += 1

        return stats
