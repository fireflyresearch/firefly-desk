# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for DocumentSourceRepository."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.models.base import Base
from flydesk.knowledge.document_source_repository import DocumentSourceRepository

_TEST_KEY = Fernet.generate_key().decode()


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def repo(session_factory):
    return DocumentSourceRepository(session_factory, encryption_key=_TEST_KEY)


class TestDocumentSourceCRUD:
    async def test_create_and_get(self, repo):
        source = await repo.create(
            source_type="s3",
            category="blob",
            display_name="My S3 Bucket",
            auth_method="credentials",
            config={
                "bucket": "my-bucket",
                "region": "us-east-1",
                "access_key_id": "AKIA...",
                "secret_access_key": "secret",
            },
        )
        assert source.id
        assert source.source_type == "s3"
        assert source.display_name == "My S3 Bucket"

        fetched = await repo.get(source.id)
        assert fetched is not None
        assert fetched.source_type == "s3"

    async def test_list_sources(self, repo):
        await repo.create(
            source_type="s3",
            category="blob",
            display_name="S3",
            auth_method="credentials",
            config={"bucket": "b"},
        )
        await repo.create(
            source_type="onedrive",
            category="drive",
            display_name="OneDrive",
            auth_method="oauth",
            config={"tenant_id": "t"},
        )
        sources = await repo.list_all()
        assert len(sources) == 2

    async def test_update_source(self, repo):
        source = await repo.create(
            source_type="s3",
            category="blob",
            display_name="Old",
            auth_method="credentials",
            config={"bucket": "b"},
        )
        updated = await repo.update(
            source.id,
            display_name="New Name",
            sync_enabled=True,
            sync_cron="0 */6 * * *",
        )
        assert updated.display_name == "New Name"
        assert updated.sync_enabled is True

    async def test_delete_source(self, repo):
        source = await repo.create(
            source_type="s3",
            category="blob",
            display_name="Delete Me",
            auth_method="credentials",
            config={"bucket": "b"},
        )
        await repo.delete(source.id)
        assert await repo.get(source.id) is None

    async def test_config_is_encrypted(self, repo):
        source = await repo.create(
            source_type="s3",
            category="blob",
            display_name="S3",
            auth_method="credentials",
            config={"secret_access_key": "super-secret"},
        )
        decrypted = await repo.get_decrypted_config(source.id)
        assert decrypted["secret_access_key"] == "super-secret"

    async def test_get_returns_masked_config(self, repo):
        source = await repo.create(
            source_type="s3",
            category="blob",
            display_name="S3",
            auth_method="credentials",
            config={"secret_access_key": "super-secret", "bucket": "my-bucket"},
        )
        fetched = await repo.get(source.id)
        assert fetched.has_config is True
        assert "secret_access_key" not in (fetched.config_summary or {})
        assert fetched.config_summary.get("bucket") == "my-bucket"

    async def test_get_nonexistent_returns_none(self, repo):
        assert await repo.get("nonexistent-id") is None

    async def test_get_decrypted_config_nonexistent_returns_none(self, repo):
        assert await repo.get_decrypted_config("nonexistent-id") is None

    async def test_update_nonexistent_returns_none(self, repo):
        assert await repo.update("nonexistent-id", display_name="X") is None

    async def test_update_config(self, repo):
        source = await repo.create(
            source_type="s3",
            category="blob",
            display_name="S3",
            auth_method="credentials",
            config={"bucket": "old-bucket"},
        )
        await repo.update(source.id, config={"bucket": "new-bucket", "region": "eu-west-1"})
        decrypted = await repo.get_decrypted_config(source.id)
        assert decrypted["bucket"] == "new-bucket"
        assert decrypted["region"] == "eu-west-1"

    async def test_list_sync_enabled(self, repo):
        await repo.create(
            source_type="s3",
            category="blob",
            display_name="No Sync",
            auth_method="credentials",
            config={"bucket": "b"},
            sync_enabled=False,
        )
        await repo.create(
            source_type="gcs",
            category="blob",
            display_name="Synced",
            auth_method="credentials",
            config={"bucket": "b"},
            sync_enabled=True,
        )
        rows = await repo.list_sync_enabled()
        assert len(rows) == 1
        assert rows[0].source_type == "gcs"
