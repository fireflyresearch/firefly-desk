# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Adapter layer: wraps Desk ToolDefinitions as genai BaseTools for FireflyAgent tool-use.

Three adapter classes bridge the Desk and GenAI tool systems:

* :class:`CatalogToolAdapter` -- wraps catalog endpoints executed via HTTP by
  :class:`~flydesk.tools.executor.ToolExecutor`.
* :class:`BuiltinToolAdapter` -- wraps platform built-in tools executed
  in-process by :class:`~flydesk.tools.builtin.BuiltinToolExecutor`.
* :class:`CustomToolAdapter` -- wraps user-defined custom tools executed in a
  subprocess sandbox by :class:`~flydesk.tools.sandbox.SandboxExecutor`.

All three convert their respective tool definitions into
:class:`~fireflyframework_genai.tools.base.BaseTool` instances so the LLM can
invoke them natively through Pydantic AI's tool-calling protocol.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import TYPE_CHECKING, Any

from fireflyframework_genai.exceptions import ToolError
from fireflyframework_genai.tools.base import BaseTool, ParameterSpec

if TYPE_CHECKING:
    from flydesk.auth.models import UserSession
    from flydesk.tools.builtin import BuiltinToolExecutor
    from flydesk.tools.custom_models import CustomTool
    from flydesk.tools.executor import ToolExecutor
    from flydesk.tools.factory import ToolDefinition
    from flydesk.tools.sandbox import SandboxExecutor

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
        # Sanitise the tool name to match the LLM API pattern ^[a-zA-Z0-9_-]{1,128}$
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", tool_def.name)[:128]
        super().__init__(
            name=safe_name,
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


class BuiltinToolAdapter(BaseTool):
    """Wraps a built-in ToolDefinition for in-process execution.

    Unlike :class:`CatalogToolAdapter` which delegates to the HTTP-based
    :class:`ToolExecutor`, this adapter calls :class:`BuiltinToolExecutor`
    which executes tools by directly calling repository methods.
    """

    def __init__(
        self,
        tool_def: ToolDefinition,
        executor: BuiltinToolExecutor,
    ) -> None:
        parameters = _build_flat_parameter_specs(tool_def)
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", tool_def.name)[:128]
        super().__init__(
            name=safe_name,
            description=tool_def.description,
            parameters=parameters,
        )
        self._tool_def = tool_def
        self._executor = executor

    async def _execute(self, **kwargs: Any) -> Any:
        """Execute via the BuiltinToolExecutor (in-process, no HTTP)."""
        result = await self._executor.execute(self._tool_def.name, kwargs)
        if "error" in result:
            raise ToolError(f"Tool {self._tool_def.name} failed: {result['error']}")
        return result


class CustomToolAdapter(BaseTool):
    """Wraps a :class:`CustomTool` for execution via subprocess sandbox.

    Unlike :class:`CatalogToolAdapter` (HTTP) and :class:`BuiltinToolAdapter`
    (in-process), this adapter delegates to :class:`SandboxExecutor` which runs
    the tool's Python code in an isolated subprocess.
    """

    def __init__(self, tool: CustomTool, sandbox: SandboxExecutor) -> None:
        parameters = _build_custom_parameter_specs(tool)
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", tool.name)[:128]
        super().__init__(name=safe_name, description=tool.description, parameters=parameters)
        self._tool = tool
        self._sandbox = sandbox

    async def _execute(self, **kwargs: Any) -> Any:
        """Execute the custom tool code in a sandboxed subprocess."""
        result = await self._sandbox.execute(
            self._tool.python_code, kwargs, timeout=self._tool.timeout_seconds,
        )
        if result.success:
            return result.data
        raise ToolError(f"Tool {self._tool.name} failed: {result.error}")


def _build_custom_parameter_specs(tool: CustomTool) -> list[ParameterSpec]:
    """Convert a :class:`CustomTool`'s ``parameters`` dict to :class:`ParameterSpec` list.

    Custom tools store parameters as a flat ``{name: info}`` dict where *info*
    is either a dict with ``type``/``description``/``required`` keys or a plain
    string used as the description.
    """
    specs: list[ParameterSpec] = []
    for param_name, param_info in tool.parameters.items():
        if isinstance(param_info, dict):
            specs.append(ParameterSpec(
                name=param_name,
                type_annotation=param_info.get("type", "str"),
                description=param_info.get("description", ""),
                required=param_info.get("required", False),
            ))
        else:
            specs.append(ParameterSpec(
                name=param_name,
                type_annotation="str",
                description=str(param_info),
                required=False,
            ))
    return specs


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
                # description may be a plain string or a nested schema dict;
                # normalise to a string in all cases.
                raw_desc = param_info.get("description", "")
                if isinstance(raw_desc, dict):
                    raw_desc = raw_desc.get("description", "") or str(raw_desc)
                specs.append(ParameterSpec(
                    name=param_name,
                    type_annotation=param_info.get("type", "str"),
                    description=str(raw_desc),
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


def _build_flat_parameter_specs(tool_def: ToolDefinition) -> list[ParameterSpec]:
    """Convert flat ToolDefinition.parameters to ParameterSpec list.

    Built-in tools use ``{param_name: {type, description, required}}`` format
    rather than the nested ``path/query/body`` sections used by catalog tools.
    """
    specs: list[ParameterSpec] = []
    for param_name, param_info in tool_def.parameters.items():
        if isinstance(param_info, dict):
            specs.append(ParameterSpec(
                name=param_name,
                type_annotation=param_info.get("type", "str"),
                description=param_info.get("description", ""),
                required=param_info.get("required", False),
            ))
    return specs


def adapt_tools(
    tool_defs: list[ToolDefinition],
    executor: ToolExecutor,
    session: UserSession,
    conversation_id: str,
    builtin_executor: BuiltinToolExecutor | None = None,
    custom_tools: list[tuple[CustomTool, SandboxExecutor]] | None = None,
) -> list[BaseTool]:
    """Convert a list of ToolDefinitions into genai-compatible BaseTool instances.

    Built-in tools (endpoint_id starting with ``__builtin__``) are wrapped in
    :class:`BuiltinToolAdapter` for in-process execution.  All other tools use
    :class:`CatalogToolAdapter` for HTTP-based execution via :class:`ToolExecutor`.

    When *custom_tools* is provided, active :class:`CustomTool` instances are
    wrapped in :class:`CustomToolAdapter` for subprocess sandbox execution.
    """
    adapted: list[BaseTool] = []
    for td in tool_defs:
        if td.endpoint_id.startswith("__builtin__") and builtin_executor is not None:
            adapted.append(BuiltinToolAdapter(td, builtin_executor))
        else:
            adapted.append(CatalogToolAdapter(td, executor, session, conversation_id))
    if custom_tools:
        for tool, sandbox in custom_tools:
            if tool.active:
                adapted.append(CustomToolAdapter(tool, sandbox))
    return adapted
