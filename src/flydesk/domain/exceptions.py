# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Domain exception hierarchy.

All domain-level errors inherit from DomainError so callers can catch
broad or narrow categories as needed.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all Flydesk domain errors."""


# -- Configuration --
class ConfigurationError(DomainError):
    """Invalid or missing configuration."""


class ProviderNotFoundError(ConfigurationError):
    """Requested provider is not registered or available."""


# -- Knowledge Pipeline --
class EmbeddingError(DomainError):
    """Embedding generation failed."""


class RetrievalError(DomainError):
    """Knowledge retrieval failed."""


class IndexingError(DomainError):
    """Document indexing failed."""


# -- Agent --
class AgentError(DomainError):
    """Agent execution error."""


class ToolExecutionError(AgentError):
    """A tool call failed during agent execution."""
