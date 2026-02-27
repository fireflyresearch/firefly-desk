# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Knowledge Graph -- entity and relation store."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.models.knowledge import EntityRow, RelationRow


@dataclass
class Entity:
    """A knowledge graph entity."""

    id: str
    entity_type: str
    name: str
    properties: dict[str, Any] = field(default_factory=dict)
    source_system: str | None = None
    confidence: float = 1.0
    mention_count: int = 1


@dataclass
class Relation:
    """A relationship between two entities."""

    source_id: str
    target_id: str
    relation_type: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


@dataclass
class EntityGraph:
    """A subgraph of entities and their relations."""

    entities: list[Entity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)


class KnowledgeGraph:
    """Entity/relation knowledge graph with text-based search."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def upsert_entity(self, entity: Entity) -> None:
        """Insert or update an entity. On update, increment mention_count."""
        async with self._session_factory() as session:
            existing = await session.get(EntityRow, entity.id)
            if existing:
                existing.name = entity.name
                existing.properties = self._to_json(entity.properties)
                existing.confidence = entity.confidence
                existing.mention_count = existing.mention_count + 1
            else:
                row = EntityRow(
                    id=entity.id,
                    entity_type=entity.entity_type,
                    name=entity.name,
                    properties=self._to_json(entity.properties),
                    source_system=entity.source_system,
                    confidence=entity.confidence,
                    mention_count=entity.mention_count,
                )
                session.add(row)
            await session.commit()

    async def get_entity(self, entity_id: str) -> Entity | None:
        """Get an entity by ID."""
        async with self._session_factory() as session:
            row = await session.get(EntityRow, entity_id)
            if row is None:
                return None
            return self._row_to_entity(row)

    async def add_relation(self, relation: Relation) -> None:
        """Add a relation between two entities."""
        async with self._session_factory() as session:
            row = RelationRow(
                source_id=relation.source_id,
                target_id=relation.target_id,
                relation_type=relation.relation_type,
                properties=self._to_json(relation.properties),
                confidence=relation.confidence,
            )
            session.add(row)
            await session.commit()

    async def find_relevant_entities(
        self, query: str, *, limit: int = 5
    ) -> list[Entity]:
        """Find entities whose name contains the query string (case-insensitive)."""
        async with self._session_factory() as session:
            # Simple LIKE-based search for SQLite compatibility
            # In production with PostgreSQL, use tsvector/GIN index
            stmt = (
                select(EntityRow)
                .where(EntityRow.name.ilike(f"%{query}%"))
                .order_by(EntityRow.mention_count.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [self._row_to_entity(r) for r in result.scalars().all()]

    async def get_entity_neighborhood(
        self, entity_id: str, *, depth: int = 1
    ) -> EntityGraph:
        """Get an entity and its immediate relations (1 level deep).

        For depth > 1, recursively fetch related entities.
        MVP supports depth=1 only for simplicity.
        """
        graph = EntityGraph()

        async with self._session_factory() as session:
            # Get the root entity
            root = await session.get(EntityRow, entity_id)
            if root is None:
                return graph
            graph.entities.append(self._row_to_entity(root))

            # Get outgoing and incoming relations
            visited = {entity_id}
            current_ids = {entity_id}

            for _ in range(depth):
                if not current_ids:
                    break

                next_ids: set[str] = set()
                for eid in current_ids:
                    # Outgoing relations
                    outgoing = await session.execute(
                        select(RelationRow).where(RelationRow.source_id == eid)
                    )
                    for rel_row in outgoing.scalars().all():
                        graph.relations.append(self._row_to_relation(rel_row))
                        if rel_row.target_id not in visited:
                            next_ids.add(rel_row.target_id)
                            visited.add(rel_row.target_id)

                    # Incoming relations
                    incoming = await session.execute(
                        select(RelationRow).where(RelationRow.target_id == eid)
                    )
                    for rel_row in incoming.scalars().all():
                        graph.relations.append(self._row_to_relation(rel_row))
                        if rel_row.source_id not in visited:
                            next_ids.add(rel_row.source_id)
                            visited.add(rel_row.source_id)

                # Fetch newly discovered entities
                for nid in next_ids:
                    entity_row = await session.get(EntityRow, nid)
                    if entity_row:
                        graph.entities.append(self._row_to_entity(entity_row))

                current_ids = next_ids

        return graph

    async def list_entities(
        self,
        *,
        query: str | None = None,
        entity_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Entity]:
        """List entities with optional search query and type filter."""
        async with self._session_factory() as session:
            stmt = select(EntityRow)
            if query:
                stmt = stmt.where(EntityRow.name.ilike(f"%{query}%"))
            if entity_type:
                stmt = stmt.where(EntityRow.entity_type == entity_type)
            stmt = (
                stmt.order_by(EntityRow.mention_count.desc())
                .offset(offset)
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [self._row_to_entity(r) for r in result.scalars().all()]

    async def list_relations(
        self,
        *,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[Relation]:
        """List all relations, ordered by source_id."""
        async with self._session_factory() as session:
            stmt = (
                select(RelationRow)
                .order_by(RelationRow.source_id)
                .offset(offset)
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [self._row_to_relation(r) for r in result.scalars().all()]

    async def delete_entity(self, entity_id: str) -> bool:
        """Delete an entity and all its relations. Returns True if entity existed."""
        async with self._session_factory() as session:
            existing = await session.get(EntityRow, entity_id)
            if existing is None:
                return False
            # Remove all relations involving this entity
            await session.execute(
                delete(RelationRow).where(RelationRow.source_id == entity_id)
            )
            await session.execute(
                delete(RelationRow).where(RelationRow.target_id == entity_id)
            )
            await session.delete(existing)
            await session.commit()
            return True

    async def get_stats(self) -> dict[str, Any]:
        """Return graph statistics: entity count, relation count, type breakdown."""
        async with self._session_factory() as session:
            # Total entity count
            entity_count_result = await session.execute(
                select(func.count()).select_from(EntityRow)
            )
            entity_count = entity_count_result.scalar() or 0

            # Total relation count
            relation_count_result = await session.execute(
                select(func.count()).select_from(RelationRow)
            )
            relation_count = relation_count_result.scalar() or 0

            # Entity type breakdown
            type_result = await session.execute(
                select(EntityRow.entity_type, func.count())
                .group_by(EntityRow.entity_type)
                .order_by(func.count().desc())
            )
            entity_types = {row[0]: row[1] for row in type_result.all()}

            # Relation type breakdown
            rel_type_result = await session.execute(
                select(RelationRow.relation_type, func.count())
                .group_by(RelationRow.relation_type)
                .order_by(func.count().desc())
            )
            relation_types = {row[0]: row[1] for row in rel_type_result.all()}

            return {
                "entity_count": entity_count,
                "relation_count": relation_count,
                "entity_types": entity_types,
                "relation_types": relation_types,
            }

    @staticmethod
    def _to_json(value: Any) -> Any:
        """Serialize to JSON string for SQLite compatibility."""
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return value

    @staticmethod
    def _from_json(value: Any) -> Any:
        """Deserialize from JSON string if needed."""
        if isinstance(value, str):
            return json.loads(value)
        return value

    @classmethod
    def _row_to_entity(cls, row: EntityRow) -> Entity:
        return Entity(
            id=row.id,
            entity_type=row.entity_type,
            name=row.name,
            properties=cls._from_json(row.properties),
            source_system=row.source_system,
            confidence=row.confidence,
            mention_count=row.mention_count,
        )

    @classmethod
    def _row_to_relation(cls, row: RelationRow) -> Relation:
        return Relation(
            id=row.id,
            source_id=row.source_id,
            target_id=row.target_id,
            relation_type=row.relation_type,
            properties=cls._from_json(row.properties),
            confidence=row.confidence,
        )
