# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Credentials Admin REST API -- CRUD for encrypted credentials."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from flydek.catalog.models import Credential

router = APIRouter(prefix="/api/credentials", tags=["credentials"])


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


async def _require_admin(request: Request) -> None:
    """Raise 403 unless the authenticated user has the 'admin' role."""
    user = getattr(request.state, "user_session", None)
    if user is None or "admin" not in user.roles:
        raise HTTPException(status_code=403, detail="Admin role required")


AdminGuard = Depends(_require_admin)
Store = Annotated[CredentialStore, Depends(get_credential_store)]


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


@router.get("", dependencies=[AdminGuard])
async def list_credentials(store: Store) -> list[dict[str, Any]]:
    """List all credentials (metadata only, encrypted values stripped)."""
    credentials = await store.list_credentials()
    return [_strip_encrypted(c) for c in credentials]


@router.post("", status_code=201, dependencies=[AdminGuard])
async def create_credential(credential: Credential, store: Store) -> Credential:
    """Store a new credential."""
    await store.create_credential(credential)
    return credential


@router.put("/{credential_id}", dependencies=[AdminGuard])
async def update_credential(
    credential_id: str, credential: Credential, store: Store
) -> Credential:
    """Update or rotate an existing credential."""
    existing = await store.get_credential(credential_id)
    if existing is None:
        raise HTTPException(
            status_code=404, detail=f"Credential {credential_id} not found"
        )
    await store.update_credential(credential)
    return credential


@router.delete("/{credential_id}", status_code=204, dependencies=[AdminGuard])
async def delete_credential(credential_id: str, store: Store) -> Response:
    """Revoke and delete a credential."""
    existing = await store.get_credential(credential_id)
    if existing is None:
        raise HTTPException(
            status_code=404, detail=f"Credential {credential_id} not found"
        )
    await store.delete_credential(credential_id)
    return Response(status_code=204)
