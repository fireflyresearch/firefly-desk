# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Adapter layer: wraps Desk ToolDefinitions as genai BaseTools for FireflyAgent tool-use.

The :class:`CatalogToolAdapter` bridges two tool systems:

* **Desk side** -- :class:`~flydesk.tools.factory.ToolDefinition` dataclasses
  executed by :class:`~flydesk.tools.executor.ToolExecutor` via HTTP.
* **GenAI side** -- :class:`~fireflyframework_genai.tools.base.BaseTool` with
  guards, parameter schemas, and automatic ``pydantic_handler()`` generation.

By wrapping each ``ToolDefinition`` in a ``CatalogToolAdapter``, the LLM can
natively invoke catalog tools through Pydantic AI's tool-calling protocol while
the existing ``ToolExecutor`` handles auth resolution, retry, rate limiting, and
audit logging.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from fireflyframework_genai.exceptions import ToolError
from fireflyframework_genai.tools.base import BaseTool, ParameterSpec

if TYPE_CHECKING:
    from flydesk.auth.models import UserSession
    from flydesk.tools.executor import ToolExecutor
    from flydesk.tools.factory import ToolDefinition

_logger = logging.getLogger(__name__)


class CatalogToolAdapter(BaseTool):
    """Wraps a Desk ToolDefinition as a genai BaseTool for FireflyAgent tool-use.

    Delegates execution to the existing :class:`ToolExecutor` so that auth
    resolution, retry policies, rate limiting, and audit logging are preserved.
    """

    def __init__(
        self,
        tool_def: ToolDefinition,
        executor: ToolExecutor,
        session: UserSession,
        conversation_id: str,
    ) -> None:
        parameters = _build_parameter_specs(tool_def)
        super().__init__(
            name=tool_def.name,
            description=tool_def.description,
            parameters=parameters,
        )
        self._tool_def = tool_def
        self._executor = executor
        self._session = session
        self._conversation_id = conversation_id

    async def _execute(self, **kwargs: Any) -> Any:
        """Execute via the existing ToolExecutor (preserves auth, retry, rate limiting).

        The LLM provides flat kwargs (e.g. ``order_id="123"``), but the
        ``ToolExecutor`` expects arguments nested by section
        (``{"path": {"order_id": "123"}, ...}``).  This method re-nests
        the flat kwargs using the ``ToolDefinition.parameters`` structure.
        """
        from flydesk.tools.executor import ToolCall

        arguments = _nest_arguments(kwargs, self._tool_def.parameters)
        arguments["_method"] = self._tool_def.method
        arguments["_system_id"] = self._tool_def.system_id

        call = ToolCall(
            call_id=str(uuid.uuid4()),
            tool_name=self._tool_def.name,
            endpoint_id=self._tool_def.endpoint_id,
            arguments=arguments,
        )
        results = await self._executor.execute_parallel(
            [call], self._session, self._conversation_id,
        )
        result = results[0]
        if result.success:
            return result.data
        raise ToolError(f"Tool {self._tool_def.name} failed: {result.error}")


def _nest_arguments(
    flat_kwargs: dict[str, Any], parameters: dict[str, Any],
) -> dict[str, Any]:
    """Re-nest flat LLM kwargs into path/query/body structure for ToolExecutor.

    The LLM sees a flat parameter list (e.g. ``order_id``, ``status``).
    The ToolExecutor expects ``{"path": {"order_id": ...}, "body": {"status": ...}}``.
    This function maps each kwarg back to its original section using the
    ``ToolDefinition.parameters`` dict as a lookup table.
    """
    nested: dict[str, Any] = {}
    claimed: set[str] = set()

    for section in ("path", "query", "body"):
        section_params = parameters.get(section, {})
        if not isinstance(section_params, dict):
            continue
        section_dict: dict[str, Any] = {}
        for param_name in section_params:
            if param_name in flat_kwargs:
                section_dict[param_name] = flat_kwargs[param_name]
                claimed.add(param_name)
        if section_dict:
            nested[section] = section_dict

    # Pass through any kwargs that don't belong to a known section
    for key, value in flat_kwargs.items():
        if key not in claimed:
            nested[key] = value

    return nested


def _build_parameter_specs(tool_def: ToolDefinition) -> list[ParameterSpec]:
    """Convert ToolDefinition.parameters dict to a list of ParameterSpec.

    The ``parameters`` dict on a :class:`ToolDefinition` may contain nested
    dicts keyed by ``"path"``, ``"query"``, and ``"body"``.  Each section maps
    parameter names to either a dict with ``type``/``description``/``required``
    keys (produced by ``ParameterDef.model_dump()``) or a plain string.

    Path parameters default to ``required=True``; query and body parameters
    default to ``required=False``.
    """
    specs: list[ParameterSpec] = []
    params = tool_def.parameters

    for section in ("path", "query", "body"):
        section_params = params.get(section, {})
        if not isinstance(section_params, dict):
            continue
        for param_name, param_info in section_params.items():
            if isinstance(param_info, dict):
                specs.append(ParameterSpec(
                    name=param_name,
                    type_annotation=param_info.get("type", "str"),
                    description=param_info.get("description", ""),
                    required=param_info.get("required", section == "path"),
                ))
            else:
                # Plain string value -- treat as description
                specs.append(ParameterSpec(
                    name=param_name,
                    type_annotation="str",
                    description=str(param_info),
                    required=section == "path",
                ))
    return specs


def adapt_tools(
    tool_defs: list[ToolDefinition],
    executor: ToolExecutor,
    session: UserSession,
    conversation_id: str,
) -> list[CatalogToolAdapter]:
    """Convert a list of ToolDefinitions into genai-compatible BaseTool instances.

    This is the main entry point used by :class:`~flydesk.agent.desk_agent.DeskAgent`
    to bridge catalog tools into the FireflyAgent tool system.
    """
    return [
        CatalogToolAdapter(td, executor, session, conversation_id)
        for td in tool_defs
    ]
