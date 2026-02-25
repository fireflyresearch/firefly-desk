# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Unified Git provider abstraction layer.

Defines a ``GitProvider`` protocol and vendor-neutral dataclasses that allow
Firefly Desk to interact with GitHub, GitLab, and Bitbucket through a single
interface.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Unified dataclasses
# ---------------------------------------------------------------------------


@dataclass
class GitAccount:
    """An organization or group that owns repositories."""

    login: str
    avatar_url: str = ""
    description: str = ""


@dataclass
class GitRepo:
    """Vendor-neutral representation of a Git repository."""

    full_name: str
    name: str
    owner: str
    private: bool
    default_branch: str
    description: str = ""
    html_url: str = ""


@dataclass
class GitBranch:
    """A branch in a Git repository."""

    name: str
    sha: str


@dataclass
class GitTreeEntry:
    """A single file entry from a recursive tree listing."""

    path: str
    sha: str
    size: int = 0
    type: str = "blob"


@dataclass
class GitFileContent:
    """Decoded content of a single file from a Git provider."""

    path: str
    sha: str
    content: str
    encoding: str = "utf-8"
    size: int = 0


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class GitProvider(Protocol):
    """Unified interface for interacting with Git hosting providers.

    Implementations must expose ``provider_type`` so callers can distinguish
    between backends without ``isinstance`` checks.
    """

    provider_type: str  # "github", "gitlab", "bitbucket"

    async def validate_token(self) -> bool:
        """Return *True* if the configured token is valid."""
        ...

    async def list_accounts(self) -> list[GitAccount]:
        """List organizations / groups the authenticated user belongs to."""
        ...

    async def list_account_repos(
        self, account: str, search: str = ""
    ) -> list[GitRepo]:
        """List repositories owned by *account* (org / group)."""
        ...

    async def list_user_repos(self, search: str = "") -> list[GitRepo]:
        """List repositories owned by the authenticated user."""
        ...

    async def list_branches(self, owner: str, repo: str) -> list[GitBranch]:
        """List branches for *owner/repo*."""
        ...

    async def list_tree(
        self, owner: str, repo: str, branch: str
    ) -> list[GitTreeEntry]:
        """Return the recursive file tree for a branch."""
        ...

    async def get_file_content(
        self, owner: str, repo: str, path: str, ref: str | None = None
    ) -> GitFileContent:
        """Fetch and decode a single file."""
        ...

    async def aclose(self) -> None:
        """Release underlying HTTP resources."""
        ...


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class GitProviderFactory:
    """Create a ``GitProvider`` instance for the requested backend."""

    _registry: dict[str, type] = {}

    @classmethod
    def register(cls, provider_type: str, adapter_cls: type) -> None:
        """Register an adapter class for *provider_type*."""
        cls._registry[provider_type] = adapter_cls

    @classmethod
    def create(
        cls,
        provider_type: str,
        token: str | None = None,
        base_url: str | None = None,
    ) -> GitProvider:
        """Return a ``GitProvider`` for *provider_type*.

        Raises ``ValueError`` if no adapter is registered for the type.
        """
        adapter_cls = cls._registry.get(provider_type)
        if adapter_cls is None:
            supported = ", ".join(sorted(cls._registry)) or "(none)"
            raise ValueError(
                f"Unsupported git provider {provider_type!r}. "
                f"Registered providers: {supported}"
            )
        return adapter_cls(token=token, base_url=base_url)
