# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Subprocess sandbox for executing custom Python tool code safely."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SandboxResult:
    """Result of a sandboxed tool execution."""

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None


class SandboxExecutor:
    """Execute Python tool code in an isolated subprocess.

    The code receives input parameters via stdin as JSON and must print
    a single JSON object to stdout.
    """

    async def execute(
        self,
        code: str,
        params: dict[str, Any],
        *,
        timeout: int = 30,
    ) -> SandboxResult:
        """Run *code* in a subprocess, passing *params* via stdin as JSON."""
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-c", code,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            input_bytes = json.dumps(params).encode()

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input=input_bytes),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return SandboxResult(success=False, error=f"Timeout after {timeout}s")

            if proc.returncode != 0:
                err_text = stderr.decode().strip()
                return SandboxResult(success=False, error=err_text or f"Exit code {proc.returncode}")

            stdout_text = stdout.decode().strip()
            if not stdout_text:
                return SandboxResult(success=False, error="No output produced")

            try:
                data = json.loads(stdout_text)
            except json.JSONDecodeError:
                return SandboxResult(
                    success=False,
                    error=f"Output is not valid JSON: {stdout_text[:200]}",
                )

            return SandboxResult(success=True, data=data)

        except Exception as exc:
            logger.error("Sandbox execution error: %s", exc, exc_info=True)
            return SandboxResult(success=False, error=str(exc))
