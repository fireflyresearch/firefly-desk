# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Concrete CredentialStore backed by the CatalogRepository."""

from __future__ import annotations

from flydesk.catalog.models import Credential
from flydesk.catalog.repository import CatalogRepository


class CatalogCredentialStore:
    """CredentialStore that delegates to CatalogRepository."""

    def __init__(self, catalog_repo: CatalogRepository) -> None:
        self._repo = catalog_repo

    async def list_credentials(self) -> list[Credential]:
        return await self._repo.list_credentials()

    async def get_credential(self, credential_id: str) -> Credential | None:
        return await self._repo.get_credential(credential_id)

    async def create_credential(self, credential: Credential) -> None:
        return await self._repo.create_credential(credential)

    async def update_credential(self, credential: Credential) -> None:
        return await self._repo.update_credential(credential)

    async def delete_credential(self, credential_id: str) -> None:
        return await self._repo.delete_credential(credential_id)
