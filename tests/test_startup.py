# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for startup validation."""
from __future__ import annotations

import pytest

from flydesk.startup import validate_startup
from flydesk.domain.exceptions import ConfigurationError


def test_validate_embedding_model_valid():
    """Valid embedding config should not raise."""
    validate_startup(embedding_model="openai:text-embedding-3-small")


def test_validate_embedding_model_invalid():
    """Invalid embedding config should raise ConfigurationError."""
    with pytest.raises(ConfigurationError, match="format"):
        validate_startup(embedding_model="no-colon-here")


def test_validate_embedding_model_empty():
    """Empty embedding config should raise ConfigurationError."""
    with pytest.raises(ConfigurationError):
        validate_startup(embedding_model="")
