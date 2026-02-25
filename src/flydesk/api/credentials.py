# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Credentials Admin REST API -- CRUD for encrypted credentials."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from flydesk.catalog.models import Credential
from flydesk.rbac.guards import CredentialsRead, CredentialsWrite

if TYPE_CHECKING:
    from flydesk.security.kms import KMSProvider

router = APIRouter(prefix="/api/credentials", tags=["credentials"])


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------


class CredentialCreate(BaseModel):
    """Request body for creating a new credential."""

    name: str
    system_id: str
    credential_type: str = "api_key"
    encrypted_value: str
    expires_at: datetime | None = None


class CredentialRotate(BaseModel):
    """Request body for rotating a credential's secret."""

    encrypted_value: str


# ---------------------------------------------------------------------------
# Credential Store interface
# ---------------------------------------------------------------------------


class CredentialStore:
    """Thin credential store interface.

    The real implementation will be backed by encrypted DB storage.
    Methods are async stubs -- overridden in production and mocked in tests.
    """

    async def list_credentials(self) -> list[Credential]:
        raise NotImplementedError

    async def get_credential(self, credential_id: str) -> Credential | None:
        raise NotImplementedError

    async def create_credential(self, credential: Credential) -> None:
        raise NotImplementedError

    async def update_credential(self, credential: Credential) -> None:
        raise NotImplementedError

    async def delete_credential(self, credential_id: str) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_credential_store() -> CredentialStore:
    """Provide a CredentialStore instance.

    In production this is wired to the real encrypted storage.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_credential_store must be overridden via app.dependency_overrides"
    )


def get_kms() -> KMSProvider:
    """Provide the KMS provider for credential encryption.

    In production this is wired to the configured KMS backend.
    In tests the dependency is overridden with a NoOpKMSProvider or mock.
    """
    from flydesk.security.kms import NoOpKMSProvider

    return NoOpKMSProvider()


Store = Annotated[CredentialStore, Depends(get_credential_store)]
KMS = Annotated["KMSProvider", Depends(get_kms)]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _strip_encrypted(credential: Credential) -> dict[str, Any]:
    """Return credential data without the encrypted_value field."""
    data = credential.model_dump(mode="json")
    data.pop("encrypted_value", None)
    return data


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/kms-status", dependencies=[CredentialsRead])
async def kms_status(kms: KMS) -> dict[str, Any]:
    """Return current KMS provider status."""
    provider_name = type(kms).__name__
    # Map class names to friendly names
    friendly = {
        "FernetKMSProvider": "fernet",
        "NoOpKMSProvider": "noop",
        "AWSKMSProvider": "aws",
        "GCPKMSProvider": "gcp",
        "AzureKeyVaultProvider": "azure",
        "VaultKMSProvider": "vault",
    }
    return {
        "provider": friendly.get(provider_name, provider_name.lower()),
        "is_dev_key": getattr(kms, "is_dev_key", False),
        "provider_class": provider_name,
    }


@router.get("", dependencies=[CredentialsRead])
async def list_credentials(store: Store) -> list[dict[str, Any]]:
    """List all credentials (metadata only, encrypted values stripped)."""
    credentials = await store.list_credentials()
    return [_strip_encrypted(c) for c in credentials]


@router.post("", status_code=201, dependencies=[CredentialsWrite])
async def create_credential(
    body: CredentialCreate, store: Store, kms: KMS
) -> dict[str, Any]:
    """Store a new credential (encrypted value is never returned)."""
    credential = Credential(
        id=str(uuid.uuid4()),
        system_id=body.system_id,
        name=body.name,
        encrypted_value=kms.encrypt(body.encrypted_value),
        credential_type=body.credential_type,
        expires_at=body.expires_at,
    )
    await store.create_credential(credential)
    return _strip_encrypted(credential)


@router.put("/{credential_id}", dependencies=[CredentialsWrite])
async def update_credential(
    credential_id: str, body: CredentialRotate, store: Store, kms: KMS
) -> dict[str, Any]:
    """Rotate an existing credential's secret value."""
    existing = await store.get_credential(credential_id)
    if existing is None:
        raise HTTPException(
            status_code=404, detail=f"Credential {credential_id} not found"
        )
    rotated = Credential(
        id=existing.id,
        system_id=existing.system_id,
        name=existing.name,
        encrypted_value=kms.encrypt(body.encrypted_value),
        credential_type=existing.credential_type,
        expires_at=existing.expires_at,
        last_rotated=datetime.now(timezone.utc),
    )
    await store.update_credential(rotated)
    return _strip_encrypted(rotated)


@router.delete("/{credential_id}", status_code=204, dependencies=[CredentialsWrite])
async def delete_credential(credential_id: str, store: Store) -> Response:
    """Revoke and delete a credential."""
    existing = await store.get_credential(credential_id)
    if existing is None:
        raise HTTPException(
            status_code=404, detail=f"Credential {credential_id} not found"
        )
    await store.delete_credential(credential_id)
    return Response(status_code=204)
