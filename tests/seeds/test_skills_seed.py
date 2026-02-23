# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for banking skill seed data.

Verifies that the skill definitions are well-formed and that the banking
seed functions correctly create and remove skills via the SkillRepository.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.models.base import Base
from flydesk.seeds.skills import (
    SKILL_ACCOUNT_LOOKUP,
    SKILL_PRODUCT_RECOMMENDATIONS,
    SKILL_REFUND_PROCESSING,
    SKILL_TICKET_MANAGEMENT,
    SKILL_TRANSACTION_HISTORY,
    SKILLS,
)
from flydesk.skills.models import Skill
from flydesk.skills.repository import SkillRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def skill_repo(session_factory):
    return SkillRepository(session_factory)


# ---------------------------------------------------------------------------
# Skill definition tests
# ---------------------------------------------------------------------------


class TestSkillDefinitions:
    """Verify the static skill definitions are well-formed."""

    def test_skills_list_has_five_entries(self):
        """There should be exactly five banking skills defined."""
        assert len(SKILLS) == 5

    def test_all_skills_are_skill_instances(self):
        """Every entry in SKILLS should be a Skill model instance."""
        for skill in SKILLS:
            assert isinstance(skill, Skill)

    def test_all_skill_ids_are_unique(self):
        """Skill IDs must be unique."""
        ids = [s.id for s in SKILLS]
        assert len(ids) == len(set(ids))

    def test_all_skill_names_are_unique(self):
        """Skill names must be unique."""
        names = [s.name for s in SKILLS]
        assert len(names) == len(set(names))

    def test_expected_skill_ids_present(self):
        """The expected skill IDs should all be present."""
        expected = {
            "skill-account-lookup",
            "skill-transaction-history",
            "skill-refund-processing",
            "skill-ticket-management",
            "skill-product-recommendations",
        }
        actual = {s.id for s in SKILLS}
        assert actual == expected

    def test_all_skills_are_active(self):
        """All seed skills should be active by default."""
        for skill in SKILLS:
            assert skill.active is True

    def test_all_skills_have_nonempty_content(self):
        """Every skill must have a non-empty content field."""
        for skill in SKILLS:
            assert skill.content.strip(), f"Skill {skill.id} has empty content"

    def test_all_skills_have_nonempty_description(self):
        """Every skill must have a non-empty description."""
        for skill in SKILLS:
            assert skill.description.strip(), f"Skill {skill.id} has empty description"

    def test_all_skills_have_tags(self):
        """Every skill should have at least one tag."""
        for skill in SKILLS:
            assert len(skill.tags) > 0, f"Skill {skill.id} has no tags"

    def test_account_lookup_references_endpoints(self):
        """Account Lookup content should reference the expected endpoints."""
        assert "ep-get-customer-profile" in SKILL_ACCOUNT_LOOKUP.content
        assert "ep-search-customers" in SKILL_ACCOUNT_LOOKUP.content

    def test_transaction_history_references_endpoints(self):
        """Transaction History content should reference the expected endpoints."""
        assert "ep-get-transactions" in SKILL_TRANSACTION_HISTORY.content
        assert "ep-get-statement" in SKILL_TRANSACTION_HISTORY.content

    def test_refund_processing_references_endpoints_and_docs(self):
        """Refund Processing content should reference endpoints and docs."""
        assert "ep-initiate-refund" in SKILL_REFUND_PROCESSING.content
        assert "doc-refund-policy" in SKILL_REFUND_PROCESSING.content

    def test_ticket_management_references_endpoints(self):
        """Ticket Management content should reference the expected endpoints."""
        assert "ep-list-tickets" in SKILL_TICKET_MANAGEMENT.content
        assert "ep-create-ticket" in SKILL_TICKET_MANAGEMENT.content
        assert "ep-close-ticket" in SKILL_TICKET_MANAGEMENT.content

    def test_product_recommendations_references_endpoints(self):
        """Product Recommendations content should reference the expected endpoints."""
        assert "ep-list-products" in SKILL_PRODUCT_RECOMMENDATIONS.content
        assert "ep-get-product-details" in SKILL_PRODUCT_RECOMMENDATIONS.content
        assert "ep-check-eligibility" in SKILL_PRODUCT_RECOMMENDATIONS.content


# ---------------------------------------------------------------------------
# Seed / unseed integration tests
# ---------------------------------------------------------------------------


class TestSeedBankingSkills:
    """Test seeding and removing skills via the banking seed functions."""

    async def test_seed_creates_skills(self, session_factory, skill_repo):
        """seed_banking_catalog with skill_repo should create all five skills."""
        from flydesk.catalog.repository import CatalogRepository
        from flydesk.seeds.banking import seed_banking_catalog

        catalog_repo = CatalogRepository(session_factory)
        await seed_banking_catalog(catalog_repo, skill_repo=skill_repo)

        skills = await skill_repo.list_skills()
        assert len(skills) == 5
        skill_ids = {s.id for s in skills}
        assert "skill-account-lookup" in skill_ids
        assert "skill-transaction-history" in skill_ids
        assert "skill-refund-processing" in skill_ids
        assert "skill-ticket-management" in skill_ids
        assert "skill-product-recommendations" in skill_ids

    async def test_seed_without_skill_repo_skips_skills(self, session_factory):
        """seed_banking_catalog without skill_repo should not fail."""
        from flydesk.catalog.repository import CatalogRepository
        from flydesk.seeds.banking import seed_banking_catalog

        catalog_repo = CatalogRepository(session_factory)
        # Should succeed without error when skill_repo is None
        await seed_banking_catalog(catalog_repo)

    async def test_unseed_removes_skills(self, session_factory, skill_repo):
        """unseed_banking_catalog with skill_repo should remove all skills."""
        from flydesk.catalog.repository import CatalogRepository
        from flydesk.seeds.banking import seed_banking_catalog, unseed_banking_catalog

        catalog_repo = CatalogRepository(session_factory)
        await seed_banking_catalog(catalog_repo, skill_repo=skill_repo)

        # Verify skills exist
        skills = await skill_repo.list_skills()
        assert len(skills) == 5

        # Unseed
        await unseed_banking_catalog(catalog_repo, skill_repo=skill_repo)

        # Verify skills removed
        skills = await skill_repo.list_skills()
        assert len(skills) == 0

    async def test_unseed_without_skill_repo_skips_skills(self, session_factory):
        """unseed_banking_catalog without skill_repo should not fail."""
        from flydesk.catalog.repository import CatalogRepository
        from flydesk.seeds.banking import seed_banking_catalog, unseed_banking_catalog

        catalog_repo = CatalogRepository(session_factory)
        await seed_banking_catalog(catalog_repo)
        # Should succeed without error when skill_repo is None
        await unseed_banking_catalog(catalog_repo)

    async def test_unseed_idempotent(self, session_factory, skill_repo):
        """Calling unseed twice should not raise errors."""
        from flydesk.catalog.repository import CatalogRepository
        from flydesk.seeds.banking import seed_banking_catalog, unseed_banking_catalog

        catalog_repo = CatalogRepository(session_factory)
        await seed_banking_catalog(catalog_repo, skill_repo=skill_repo)
        await unseed_banking_catalog(catalog_repo, skill_repo=skill_repo)
        # Second unseed should be safe (skills already absent)
        await unseed_banking_catalog(catalog_repo, skill_repo=skill_repo)

        skills = await skill_repo.list_skills()
        assert len(skills) == 0

    async def test_seeded_skills_are_active(self, session_factory, skill_repo):
        """All seeded skills should be active."""
        from flydesk.catalog.repository import CatalogRepository
        from flydesk.seeds.banking import seed_banking_catalog

        catalog_repo = CatalogRepository(session_factory)
        await seed_banking_catalog(catalog_repo, skill_repo=skill_repo)

        skills = await skill_repo.list_skills(active_only=True)
        assert len(skills) == 5

    async def test_seeded_skills_have_content(self, session_factory, skill_repo):
        """Each seeded skill should have non-empty content in the database."""
        from flydesk.catalog.repository import CatalogRepository
        from flydesk.seeds.banking import seed_banking_catalog

        catalog_repo = CatalogRepository(session_factory)
        await seed_banking_catalog(catalog_repo, skill_repo=skill_repo)

        for skill_def in SKILLS:
            skill = await skill_repo.get_skill(skill_def.id)
            assert skill is not None, f"Skill {skill_def.id} not found"
            assert skill.content.strip(), f"Skill {skill_def.id} has empty content"
            assert skill.name == skill_def.name
