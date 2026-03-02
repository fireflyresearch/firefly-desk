# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Admin API endpoints for model routing configuration."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from flydesk.agent.router.config import RoutingConfigRepository
from flydesk.agent.router.models import RoutingConfig
from flydesk.api.deps import get_routing_config_repo
from flydesk.rbac.guards import require_permission

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/model-routing", tags=["model-routing"])

AdminLLM = require_permission("admin:llm")
Repo = Annotated[RoutingConfigRepository, Depends(get_routing_config_repo)]


@router.get("", dependencies=[AdminLLM])
async def get_routing_config(repo: Repo) -> dict[str, Any]:
    """Get current model routing configuration."""
    config = await repo.get_config()
    if config is None:
        return RoutingConfig().model_dump()
    return config.model_dump()


@router.put("", dependencies=[AdminLLM])
async def update_routing_config(
    body: RoutingConfig,
    repo: Repo,
) -> dict[str, Any]:
    """Update model routing configuration."""
    updated = await repo.update_config(body)
    return updated.model_dump()


@router.post("/test", dependencies=[AdminLLM])
async def test_classifier(
    body: dict[str, Any],
    repo: Repo,
) -> dict[str, Any]:
    """Test the classifier with a sample message.

    Body: {"message": "Hello!", "tool_count": 5, "tool_names": ["search"]}
    """
    config = await repo.get_config()
    if config is None or not config.enabled:
        return {"error": "Routing is not enabled", "config": RoutingConfig().model_dump()}

    return {
        "message": body.get("message", ""),
        "note": "Full classifier test requires agent_factory — use the admin UI for live testing",
        "config": config.model_dump(),
    }
