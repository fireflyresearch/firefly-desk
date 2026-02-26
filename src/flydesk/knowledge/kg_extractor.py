# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Knowledge-graph entity and relation extraction using LLM.

``KGExtractor`` uses ``DeskAgentFactory`` (fireflyframework-genai) to call an
LLM that identifies entities and relationships from unstructured documents or
structured catalog system descriptions.
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, Field

from flydesk.knowledge.analyzer import _MAX_CONTENT_LENGTH

if TYPE_CHECKING:
    from flydesk.agent.genai_bridge import DeskAgentFactory

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic models for structured LLM output
# ---------------------------------------------------------------------------


class ExtractedEntity(BaseModel):
    """A single entity extracted by the LLM."""

    name: str
    entity_type: str
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0


class ExtractedRelation(BaseModel):
    """A single relation extracted by the LLM."""

    source: str
    target: str
    relation_type: str
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0


class KGExtractionResult(BaseModel):
    """Top-level LLM response schema for entity/relation extraction."""

    entities: list[ExtractedEntity] = Field(default_factory=list)
    relations: list[ExtractedRelation] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Prompt templates directory
# ---------------------------------------------------------------------------

_PROMPTS_DIR = Path(__file__).parent / "prompts"


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------


class KGExtractor:
    """Extracts knowledge graph entities and relations using an LLM.

    Uses ``DeskAgentFactory`` to create a temporary ``FireflyAgent`` for each
    extraction call. If no LLM provider is configured, extraction returns
    empty lists.
    """

    def __init__(
        self,
        agent_factory: DeskAgentFactory,
        *,
        prompts_dir: Path | None = None,
    ) -> None:
        self._agent_factory = agent_factory
        templates_path = prompts_dir or _PROMPTS_DIR
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(templates_path)),
            autoescape=False,
        )

    async def extract_from_document(
        self,
        content: str,
        title: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Extract entities and relations from a knowledge document.

        Returns:
            A tuple of ``(entities, relations)`` where each item is a list
            of dicts suitable for ``KnowledgeGraph.upsert_entity()`` and
            ``KnowledgeGraph.add_relation()``.
        """
        system_prompt = self._render_document_system()
        user_prompt = self._render_document_user(
            title=title,
            content=content[:_MAX_CONTENT_LENGTH],
        )
        return await self._extract(system_prompt, user_prompt, source_system=None)

    async def extract_from_catalog(
        self,
        system_name: str,
        system_description: str,
        base_url: str,
        status: str,
        tags: list[str],
        endpoints: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Extract entities and relations from a catalog system definition.

        Returns:
            A tuple of ``(entities, relations)``.
        """
        endpoint_lines = []
        for ep in endpoints:
            endpoint_lines.append(
                f"  - {ep.get('method', 'GET')} {ep.get('path', '/')} "
                f"-- {ep.get('name', '')} ({ep.get('description', '')})"
            )
        endpoints_text = "\n".join(endpoint_lines) if endpoint_lines else "  (none)"

        system_prompt = self._render_catalog_system()
        user_prompt = self._render_catalog_user(
            name=system_name,
            description=system_description,
            base_url=base_url,
            status=status,
            tags=", ".join(tags),
            endpoints=endpoints_text,
        )
        return await self._extract(system_prompt, user_prompt, source_system=system_name)

    # ------------------------------------------------------------------
    # Prompt rendering
    # ------------------------------------------------------------------

    def _render_document_system(self) -> str:
        """Render the document extraction system prompt template."""
        template = self._jinja_env.get_template("kg_extraction_document_system.j2")
        return template.render()

    def _render_document_user(self, title: str, content: str) -> str:
        """Render the document extraction user prompt template."""
        template = self._jinja_env.get_template("kg_extraction_document_user.j2")
        return template.render(title=title, content=content)

    def _render_catalog_system(self) -> str:
        """Render the catalog extraction system prompt template."""
        template = self._jinja_env.get_template("kg_extraction_catalog_system.j2")
        return template.render()

    def _render_catalog_user(
        self,
        name: str,
        description: str,
        base_url: str,
        status: str,
        tags: str,
        endpoints: str,
    ) -> str:
        """Render the catalog extraction user prompt template."""
        template = self._jinja_env.get_template("kg_extraction_catalog_user.j2")
        return template.render(
            name=name,
            description=description,
            base_url=base_url,
            status=status,
            tags=tags,
            endpoints=endpoints,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _extract(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        source_system: str | None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Call the LLM and parse the response into entities and relations."""
        agent = await self._agent_factory.create_agent(system_prompt)
        if agent is None:
            logger.warning("No LLM provider configured; KG extraction skipped.")
            return [], []

        try:
            result = await agent.run(user_prompt)
            output_text = str(result.output)
        except Exception:
            logger.exception("LLM call failed during KG extraction.")
            return [], []

        extraction = self._parse_response(output_text)

        # Convert to dicts with generated IDs, suitable for KnowledgeGraph
        entity_name_to_id: dict[str, str] = {}
        entity_dicts: list[dict[str, Any]] = []
        for ent in extraction.entities:
            entity_id = str(uuid.uuid4())
            entity_name_to_id[ent.name] = entity_id
            entity_dicts.append(
                {
                    "id": entity_id,
                    "entity_type": ent.entity_type,
                    "name": ent.name,
                    "properties": ent.properties,
                    "source_system": source_system,
                    "confidence": ent.confidence,
                }
            )

        relation_dicts: list[dict[str, Any]] = []
        for rel in extraction.relations:
            source_id = entity_name_to_id.get(rel.source)
            target_id = entity_name_to_id.get(rel.target)
            if source_id is None or target_id is None:
                logger.debug(
                    "Skipping relation %s -> %s (entity not found in extraction)",
                    rel.source,
                    rel.target,
                )
                continue
            relation_dicts.append(
                {
                    "source_id": source_id,
                    "target_id": target_id,
                    "relation_type": rel.relation_type,
                    "properties": rel.properties,
                    "confidence": rel.confidence,
                }
            )

        return entity_dicts, relation_dicts

    @staticmethod
    def _parse_response(text: str) -> KGExtractionResult:
        """Parse the LLM text response as JSON into a ``KGExtractionResult``.

        Handles markdown code blocks and malformed JSON gracefully.
        """
        cleaned = text.strip()

        # Strip markdown code blocks if present
        if cleaned.startswith("```"):
            first_newline = cleaned.index("\n") if "\n" in cleaned else len(cleaned)
            cleaned = cleaned[first_newline + 1 :]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Failed to parse KG extraction response as JSON: %s...", cleaned[:200])
            return KGExtractionResult()

        try:
            return KGExtractionResult.model_validate(data)
        except Exception:
            logger.warning("KG extraction JSON did not match expected schema.", exc_info=True)
            return KGExtractionResult()
