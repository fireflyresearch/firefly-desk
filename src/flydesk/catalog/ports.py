# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Port interfaces for the catalog domain."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from flydesk.catalog.models import Credential


@runtime_checkable
class CredentialStore(Protocol):
    """Port for credential storage operations."""

    async def list_credentials(self) -> list[Credential]: ...
    async def get_credential(self, credential_id: str) -> Credential | None: ...
    async def create_credential(self, credential: Credential) -> None: ...
    async def update_credential(self, credential: Credential) -> None: ...
    async def delete_credential(self, credential_id: str) -> None: ...
