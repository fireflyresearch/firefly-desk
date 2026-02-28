"""Verify domain exception hierarchy."""
from flydesk.domain.exceptions import (
    DomainError,
    ConfigurationError,
    ProviderNotFoundError,
    EmbeddingError,
    RetrievalError,
    IndexingError,
    AgentError,
    ToolExecutionError,
)


def test_domain_error_is_base():
    assert issubclass(ConfigurationError, DomainError)
    assert issubclass(EmbeddingError, DomainError)
    assert issubclass(AgentError, DomainError)


def test_provider_not_found_inherits_configuration():
    assert issubclass(ProviderNotFoundError, ConfigurationError)


def test_tool_execution_inherits_agent():
    assert issubclass(ToolExecutionError, AgentError)


def test_exceptions_carry_message():
    exc = EmbeddingError("bad embedding")
    assert str(exc) == "bad embedding"
