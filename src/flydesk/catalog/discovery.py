# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""System Discovery LLM Analysis Engine.

Uses fireflyframework-genai (via ``DeskAgentFactory``) to analyze knowledge
graph entities, relations, and knowledge base documents to automatically
discover external systems that should be added to the service catalog.
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

from flydesk.catalog.enums import AuthType, HttpMethod, RiskLevel, SystemStatus
from flydesk.catalog.models import AuthConfig, ExternalSystem, ServiceEndpoint
from flydesk.jobs.handlers import ProgressCallback

if TYPE_CHECKING:
    from flydesk.agent.genai_bridge import DeskAgentFactory
    from flydesk.catalog.repository import CatalogRepository
    from flydesk.jobs.models import Job
    from flydesk.jobs.runner import JobRunner
    from flydesk.knowledge.graph import KnowledgeGraph

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic models for parsing the LLM's structured JSON response
# ---------------------------------------------------------------------------

_PROMPTS_DIR = Path(__file__).parent / "discovery_prompts"


class DiscoveredEndpoint(BaseModel):
    """An endpoint discovered from document analysis."""

    name: str
    method: str = "GET"
    path: str = ""
    description: str = ""
    parameters: list[dict[str, str]] = Field(default_factory=list)


class DiscoveredSystem(BaseModel):
    """A single system from the LLM discovery response."""

    name: str
    description: str = ""
    base_url: str = ""
    category: str = ""
    auth_type: str = "none"
    confidence: float = 0.0
    tags: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    endpoints: list[DiscoveredEndpoint] = Field(default_factory=list)
    config_parameters: list[dict[str, str]] = Field(default_factory=list)


class SystemDiscoveryResult(BaseModel):
    """Top-level LLM response schema for system discovery."""

    systems: list[DiscoveredSystem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Context data containers
# ---------------------------------------------------------------------------


@dataclass
class ExistingSystemContext:
    """Flattened existing system for deduplication in templates."""

    name: str
    description: str


@dataclass
class SystemDiscoveryContext:
    """All gathered context fed into the LLM prompt."""

    systems: list[ExistingSystemContext] = field(default_factory=list)
    entities: list[dict[str, Any]] = field(default_factory=list)
    relations: list[dict[str, Any]] = field(default_factory=list)
    documents: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class SystemDiscoveryEngine:
    """Discovers external systems by analyzing enterprise context with an LLM.

    Orchestrates the full discovery flow:
    1. Gather context from catalog, knowledge graph, and knowledge base
    2. Build structured prompts from Jinja2 templates
    3. Call an LLM via ``DeskAgentFactory`` (fireflyframework-genai)
    4. Parse the structured JSON response into ``ExternalSystem`` models
    5. Merge with existing systems (skip existing, never overwrite)
    6. Persist via ``CatalogRepository``
    """

    def __init__(
        self,
        agent_factory: DeskAgentFactory,
        catalog_repo: CatalogRepository,
        knowledge_graph: KnowledgeGraph,
        *,
        prompts_dir: Path | None = None,
    ) -> None:
        self._agent_factory = agent_factory
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

    async def discover(self, trigger: str, job_runner: JobRunner) -> Job:
        """Submit a system discovery job to the background job runner.

        Parameters:
            trigger: Human-readable trigger description (e.g. "New KB documents uploaded").
            job_runner: The ``JobRunner`` instance to submit the job to.

        Returns:
            The created ``Job`` domain object for tracking.
        """
        payload = {"trigger": trigger}
        return await job_runner.submit("system_discovery", payload)

    # ------------------------------------------------------------------
    # Analysis (called by SystemDiscoveryHandler)
    # ------------------------------------------------------------------

    async def _analyze(
        self,
        job_id: str,
        payload: dict,
        on_progress: ProgressCallback,
    ) -> dict:
        """Run the full system discovery analysis pipeline.

        This method is invoked by ``SystemDiscoveryHandler.execute()``.

        Returns a summary dict to be stored as the job result.
        """
        trigger = payload.get("trigger", "")
        await on_progress(5, "Scanning catalog systems, knowledge graph, and documents...")

        # 1. Gather context
        context = await self._gather_context()
        await on_progress(
            20,
            f"Context gathered: {len(context.systems)} existing systems, "
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
                "systems_discovered": 0,
            }

        # Build a summary of discovered systems with names and confidence
        sys_count = len(discovery_result.systems)
        if sys_count > 0:
            sys_summaries = [
                f"{s.name} ({int(s.confidence * 100)}%)"
                for s in discovery_result.systems[:8]
            ]
            sys_list = ", ".join(sys_summaries)
            if sys_count > 8:
                sys_list += f", ... and {sys_count - 8} more"
            await on_progress(60, f"LLM identified {sys_count} systems: {sys_list}")
        else:
            await on_progress(60, "LLM analysis complete — no systems identified")

        # 4. Filter by quality gate, then convert to domain models
        qualified = [s for s in discovery_result.systems if self._should_create(s)]
        discovered = self._to_external_systems(SystemDiscoveryResult(systems=qualified))
        await on_progress(70, "Merging discovered systems with existing catalog...")

        # 5. Merge with existing
        stats = await self._merge_systems(discovered)
        merge_parts = []
        if stats["created"]:
            merge_parts.append(f"{stats['created']} new")
        if stats["skipped"]:
            merge_parts.append(f"{stats['skipped']} already in catalog")
        merge_summary = ", ".join(merge_parts) if merge_parts else "no changes"
        await on_progress(95, f"Merge complete: {merge_summary}")

        result = {
            "status": "completed",
            "trigger": trigger,
            "systems_discovered": stats["discovered"],
            "systems_created": stats["created"],
            "systems_skipped": stats["skipped"],
        }
        await on_progress(
            100,
            f"Discovery complete — {stats['discovered']} systems discovered, "
            f"{stats['created']} created, {stats['skipped']} already existed",
        )
        return result

    # ------------------------------------------------------------------
    # Context gathering
    # ------------------------------------------------------------------

    async def _gather_context(self) -> SystemDiscoveryContext:
        """Collect all available enterprise context for the LLM prompt."""
        ctx = SystemDiscoveryContext()

        # Existing catalog systems (for deduplication)
        try:
            systems, _ = await self._catalog_repo.list_systems()
            for sys in systems:
                ctx.systems.append(
                    ExistingSystemContext(
                        name=sys.name,
                        description=sys.description,
                    )
                )
        except Exception:
            logger.warning("Failed to gather existing catalog systems.", exc_info=True)

        # Knowledge graph entities + relations
        try:
            entities = await self._knowledge_graph.list_entities(limit=200)
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
            documents = await self._catalog_repo.list_knowledge_documents()
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
        template = self._jinja_env.get_template("system_discovery_system.j2")
        return template.render(trigger=trigger)

    def _render_context_prompt(self, context: SystemDiscoveryContext) -> str:
        """Render the context template with gathered data."""
        template = self._jinja_env.get_template("system_discovery_context.j2")
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
    ) -> SystemDiscoveryResult | None:
        """Call the LLM and parse the response into a ``SystemDiscoveryResult``.

        Returns ``None`` if no LLM provider is configured.
        Raises no exceptions -- returns an empty result on parse errors.
        """
        # System discovery generates large JSON responses -- use a higher token
        # limit than the default chat agent to avoid truncation.
        agent = await self._agent_factory.create_agent(
            system_prompt,
            model_settings_override={"max_tokens": 16384},
        )
        if agent is None:
            logger.warning("No LLM provider configured; system discovery skipped.")
            return None

        try:
            result = await agent.run(user_prompt)
            output_text = str(result.output)
        except Exception:
            logger.exception("LLM call failed during system discovery.")
            return SystemDiscoveryResult(systems=[])

        return self._parse_llm_response(output_text)

    @staticmethod
    def _parse_llm_response(text: str) -> SystemDiscoveryResult:
        """Parse the LLM's text response as JSON into a ``SystemDiscoveryResult``.

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
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response as JSON: %s...", cleaned[:200])
            return SystemDiscoveryResult(systems=[])

        try:
            return SystemDiscoveryResult.model_validate(data)
        except Exception:
            logger.warning("LLM JSON did not match SystemDiscoveryResult schema.", exc_info=True)
            return SystemDiscoveryResult(systems=[])

    # ------------------------------------------------------------------
    # Domain model conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _to_external_systems(result: SystemDiscoveryResult) -> list[ExternalSystem]:
        """Convert parsed LLM output to ``ExternalSystem`` domain models."""
        systems: list[ExternalSystem] = []
        for disc_sys in result.systems:
            system_id = str(uuid.uuid4())

            # Resolve auth_type safely -- default to NONE for unrecognised values
            try:
                auth_type = AuthType(disc_sys.auth_type)
            except ValueError:
                auth_type = AuthType.NONE

            systems.append(
                ExternalSystem(
                    id=system_id,
                    name=disc_sys.name,
                    description=disc_sys.description,
                    base_url=disc_sys.base_url,
                    status=SystemStatus.DRAFT,
                    auth_config=AuthConfig(auth_type=auth_type),
                    agent_enabled=False,
                    tags=disc_sys.tags,
                    metadata={
                        "source": "auto_discovered",
                        "confidence": disc_sys.confidence,
                        "category": disc_sys.category,
                        "evidence": disc_sys.evidence,
                        "discovered_endpoints": [ep.model_dump() for ep in disc_sys.endpoints],
                        "config_parameters": disc_sys.config_parameters,
                    },
                )
            )
        return systems

    # ------------------------------------------------------------------
    # Quality gate
    # ------------------------------------------------------------------

    @staticmethod
    def _should_create(system: DiscoveredSystem) -> bool:
        """Only create systems with sufficient evidence."""
        if system.confidence < 0.5:
            return False
        has_endpoints = len(system.endpoints) > 0
        has_url = bool(system.base_url)
        has_high_confidence = system.confidence >= 0.8
        return has_endpoints or has_url or has_high_confidence

    # ------------------------------------------------------------------
    # Merge strategy
    # ------------------------------------------------------------------

    async def _merge_systems(
        self,
        discovered: list[ExternalSystem],
    ) -> dict[str, int]:
        """Merge discovered systems with existing ones.

        Merge rules:
        - Existing systems are NEVER overwritten or deleted
        - Case-insensitive name match is used for deduplication
        - Brand new systems are created with status DRAFT

        Returns a stats dict with counts.
        """
        stats = {"discovered": len(discovered), "created": 0, "skipped": 0}

        existing, _ = await self._catalog_repo.list_systems()
        existing_by_name: dict[str, ExternalSystem] = {
            s.name.lower(): s for s in existing
        }

        for system in discovered:
            existing_system = existing_by_name.get(system.name.lower())

            if existing_system is None:
                # Brand new system -- create it
                await self._catalog_repo.create_system(system)
                stats["created"] += 1

                # Auto-create discovered endpoints
                for ep_data in system.metadata.get("discovered_endpoints", []):
                    # Resolve HTTP method safely -- default to GET
                    try:
                        method = HttpMethod(ep_data.get("method", "GET").upper())
                    except ValueError:
                        method = HttpMethod.GET

                    endpoint = ServiceEndpoint(
                        id=str(uuid.uuid4()),
                        system_id=system.id,
                        name=ep_data.get("name", ""),
                        description=ep_data.get("description", ""),
                        method=method,
                        path=ep_data.get("path", ""),
                        when_to_use=ep_data.get("description", ""),
                        risk_level=RiskLevel.READ,
                        required_permissions=[],
                    )
                    await self._catalog_repo.create_endpoint(endpoint)
            else:
                # System already exists -- never overwrite
                logger.debug(
                    "Skipping discovered system '%s' — already exists as '%s' (id=%s)",
                    system.name,
                    existing_system.name,
                    existing_system.id,
                )
                stats["skipped"] += 1

        return stats
