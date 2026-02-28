"""Domain exception hierarchy.

All domain-level errors inherit from DomainError so callers can catch
broad or narrow categories as needed.
"""


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
