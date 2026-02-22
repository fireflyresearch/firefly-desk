# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for KnowledgeGraph entity/relation store."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.knowledge.graph import Entity, KnowledgeGraph, Relation
from flydesk.models.base import Base


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def kg(session_factory) -> KnowledgeGraph:
    return KnowledgeGraph(session_factory)


@pytest.fixture
def sample_entity() -> Entity:
    return Entity(
        id="acme-corp",
        entity_type="company",
        name="Acme Corporation",
        properties={"industry": "technology", "founded": 1990},
        source_system="crm",
        confidence=0.95,
    )


class TestKnowledgeGraph:
    async def test_upsert_entity_creates_new(self, kg, sample_entity):
        await kg.upsert_entity(sample_entity)

        result = await kg.get_entity("acme-corp")
        assert result is not None
        assert result.id == "acme-corp"
        assert result.entity_type == "company"
        assert result.name == "Acme Corporation"
        assert result.properties == {"industry": "technology", "founded": 1990}
        assert result.source_system == "crm"
        assert result.confidence == 0.95
        assert result.mention_count == 1

    async def test_upsert_entity_updates_existing(self, kg, sample_entity):
        await kg.upsert_entity(sample_entity)
        # Upsert again -- should increment mention_count
        sample_entity.name = "Acme Corp (Updated)"
        sample_entity.confidence = 0.99
        await kg.upsert_entity(sample_entity)

        result = await kg.get_entity("acme-corp")
        assert result is not None
        assert result.name == "Acme Corp (Updated)"
        assert result.confidence == 0.99
        assert result.mention_count == 2

    async def test_get_entity_not_found(self, kg):
        result = await kg.get_entity("nonexistent")
        assert result is None

    async def test_add_relation(self, kg):
        # Create two entities
        alice = Entity(id="alice", entity_type="person", name="Alice")
        bob = Entity(id="bob", entity_type="person", name="Bob")
        await kg.upsert_entity(alice)
        await kg.upsert_entity(bob)

        # Add relation
        rel = Relation(
            source_id="alice",
            target_id="bob",
            relation_type="works_with",
            properties={"since": "2024"},
            confidence=0.9,
        )
        await kg.add_relation(rel)

        # Verify via neighborhood
        graph = await kg.get_entity_neighborhood("alice")
        assert len(graph.relations) == 1
        assert graph.relations[0].source_id == "alice"
        assert graph.relations[0].target_id == "bob"
        assert graph.relations[0].relation_type == "works_with"
        assert graph.relations[0].properties == {"since": "2024"}
        assert graph.relations[0].confidence == 0.9

    async def test_find_relevant_entities(self, kg):
        await kg.upsert_entity(Entity(id="e1", entity_type="company", name="Acme Corporation"))
        await kg.upsert_entity(Entity(id="e2", entity_type="person", name="Alice Smith"))
        await kg.upsert_entity(Entity(id="e3", entity_type="company", name="acme widgets"))

        # Case-insensitive search for "acme"
        results = await kg.find_relevant_entities("acme")
        assert len(results) == 2
        names = {r.name for r in results}
        assert "Acme Corporation" in names
        assert "acme widgets" in names

    async def test_find_relevant_entities_ordered_by_mentions(self, kg):
        e1 = Entity(id="e1", entity_type="company", name="Acme One")
        e2 = Entity(id="e2", entity_type="company", name="Acme Two")

        await kg.upsert_entity(e1)
        await kg.upsert_entity(e2)
        # Upsert e2 twice more to boost mention_count to 3
        await kg.upsert_entity(e2)
        await kg.upsert_entity(e2)

        results = await kg.find_relevant_entities("acme")
        assert len(results) == 2
        # e2 should come first -- higher mention_count (3 vs 1)
        assert results[0].id == "e2"
        assert results[0].mention_count == 3
        assert results[1].id == "e1"
        assert results[1].mention_count == 1

    async def test_get_entity_neighborhood(self, kg):
        # Build a small graph: A --manages--> B, C --reports_to--> A
        a = Entity(id="a", entity_type="person", name="Alice")
        b = Entity(id="b", entity_type="person", name="Bob")
        c = Entity(id="c", entity_type="person", name="Charlie")
        await kg.upsert_entity(a)
        await kg.upsert_entity(b)
        await kg.upsert_entity(c)

        await kg.add_relation(Relation(source_id="a", target_id="b", relation_type="manages"))
        await kg.add_relation(Relation(source_id="c", target_id="a", relation_type="reports_to"))

        graph = await kg.get_entity_neighborhood("a")

        # Should include a, b, c
        entity_ids = {e.id for e in graph.entities}
        assert entity_ids == {"a", "b", "c"}

        # Should include both relations
        assert len(graph.relations) == 2
        rel_types = {(r.source_id, r.target_id, r.relation_type) for r in graph.relations}
        assert ("a", "b", "manages") in rel_types
        assert ("c", "a", "reports_to") in rel_types

    async def test_get_entity_neighborhood_missing_entity(self, kg):
        graph = await kg.get_entity_neighborhood("nonexistent")
        assert graph.entities == []
        assert graph.relations == []
