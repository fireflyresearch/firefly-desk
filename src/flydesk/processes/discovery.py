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
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, Field

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
        prompts_dir: Path | None = None,
    ) -> None:
        self._agent_factory = agent_factory
        self._process_repo = process_repo
        self._catalog_repo = catalog_repo
        self._knowledge_graph = knowledge_graph

        templates_path = prompts_dir or _PROMPTS_DIR
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(templates_path)),
            autoescape=False,
        )

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
        )
        # Build a descriptive summary of what was gathered
        total_endpoints = sum(len(s.endpoints) for s in context.systems)
        await on_progress(
            20,
            f"Context gathered: {len(context.systems)} systems, "
            f"{total_endpoints} endpoints, "
            f"{len(context.entities)} entities, "
            f"{len(context.relations)} relations, "
            f"{len(context.documents)} documents",
        )

        # 2. Build prompt
        system_prompt = self._render_system_prompt(trigger)
        user_prompt = self._render_context_prompt(context)
        prompt_size = len(system_prompt) + len(user_prompt)
        await on_progress(
            25,
            f"Sending {prompt_size:,} characters of context to LLM for analysis...",
        )

        # 3. Call LLM
        discovery_result = await self._call_llm(system_prompt, user_prompt)
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
            await on_progress(60, "LLM analysis complete — no processes identified")

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

        result = {
            "status": "completed",
            "trigger": trigger,
            "processes_discovered": stats["discovered"],
            "processes_created": stats["created"],
            "processes_updated": stats["updated"],
            "processes_skipped": stats["skipped"],
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
    ) -> DiscoveryContext:
        """Collect all available enterprise context for the LLM prompt."""
        ctx = DiscoveryContext()

        # Catalog systems + endpoints
        try:
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
            for sys in systems:
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
        except Exception:
            logger.warning("Failed to gather catalog context.", exc_info=True)

        # Knowledge graph entities + relations
        try:
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
        except Exception:
            logger.warning("Failed to gather knowledge graph context.", exc_info=True)

        # Knowledge base documents
        try:
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

            if document_types:
                type_set = set(document_types)
                documents = [
                    doc for doc in documents
                    if str(getattr(doc, "document_type", "other")) in type_set
                ]

            ctx.documents = [
                {
                    "title": getattr(doc, "title", ""),
                    "document_type": str(getattr(doc, "document_type", "other")),
                    "tags": getattr(doc, "tags", []),
                    "content": getattr(doc, "content", ""),
                }
                for doc in documents
            ]
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
    ) -> DiscoveryResult | None:
        """Call the LLM and parse the response into a ``DiscoveryResult``.

        Returns ``None`` if no LLM provider is configured.
        Raises no exceptions -- returns an empty result on parse errors.
        """
        # Process discovery generates large JSON responses -- use a higher token
        # limit than the default chat agent to avoid truncation.
        agent = await self._agent_factory.create_agent(
            system_prompt,
            model_settings_override={"max_tokens": 16384},
        )
        if agent is None:
            logger.warning("No LLM provider configured; process discovery skipped.")
            return None

        try:
            result = await agent.run(user_prompt)
            output_text = str(result.output)
        except Exception:
            logger.exception("LLM call failed during process discovery.")
            return DiscoveryResult(processes=[])

        return self._parse_llm_response(output_text)

    @staticmethod
    def _parse_llm_response(text: str) -> DiscoveryResult:
        """Parse the LLM's text response as JSON into a ``DiscoveryResult``.

        Handles common LLM formatting quirks like markdown code blocks.
        Returns an empty result on malformed responses.
        """
        cleaned = text.strip()

        # Strip markdown code blocks if present
        if cleaned.startswith("```"):
            # Remove opening fence (e.g. ```json or ```)
            first_newline = cleaned.index("\n") if "\n" in cleaned else len(cleaned)
            cleaned = cleaned[first_newline + 1 :]
            if cleaned.endswith("```"):
                cleaned = cleaned[: -3]
            cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response as JSON: %s...", cleaned[:200])
            return DiscoveryResult(processes=[])

        try:
            return DiscoveryResult.model_validate(data)
        except Exception:
            logger.warning("LLM JSON did not match DiscoveryResult schema.", exc_info=True)
            return DiscoveryResult(processes=[])

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
        existing_by_name: dict[str, BusinessProcess] = {p.name: p for p in existing}

        for proc in discovered:
            existing_proc = existing_by_name.get(proc.name)

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
