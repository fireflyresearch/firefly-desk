# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Load Desk prompt templates from disk and register them."""

from __future__ import annotations

from pathlib import Path

from fireflyframework_genai.prompts import PromptLoader, PromptRegistry


def register_desk_prompts(prompts_dir: Path | None = None) -> PromptRegistry:
    """Load all ``.j2`` templates and return a populated :class:`PromptRegistry`.

    Parameters:
        prompts_dir: Override directory containing the Jinja2 template files.
            Defaults to the ``templates/`` subdirectory next to this module.
    """
    base = prompts_dir or Path(__file__).parent / "templates"
    registry = PromptRegistry()
    for template in PromptLoader.from_directory(base, glob_pattern="*.j2"):
        registry.register(template)
    return registry
