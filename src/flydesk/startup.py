# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Startup validation for Flydesk server.

Called early in the lifespan to fail fast with actionable error messages.
"""
from __future__ import annotations

import logging

from flydesk.domain.exceptions import ConfigurationError
from flydesk.knowledge.embedding_factory import parse_embedding_config

_logger = logging.getLogger(__name__)


def validate_startup(
    *,
    embedding_model: str = "",
    warn_no_llm: bool = True,
) -> None:
    """Validate configuration at startup. Raises ConfigurationError on failure."""

    # Validate embedding model format
    if embedding_model:
        parse_embedding_config(embedding_model)  # raises ConfigurationError if bad
    else:
        raise ConfigurationError(
            "embedding_model is required. "
            "Set it to 'provider:model' (e.g., 'openai:text-embedding-3-small')."
        )
