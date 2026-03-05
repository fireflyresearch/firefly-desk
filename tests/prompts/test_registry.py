"""Tests for the Desk prompt registry: template loading, rendering, variable injection."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from fireflyframework_genai.exceptions import PromptNotFoundError
from fireflyframework_genai.prompts import PromptLoader, PromptRegistry, PromptTemplate
from flydesk.prompts.registry import register_desk_prompts


# ---------------------------------------------------------------------------
# PromptRegistry (from fireflyframework_genai, exercised through flydesk)
# ---------------------------------------------------------------------------

class TestPromptRegistryBasics:
    def test_register_and_get(self):
        """Register a template and retrieve it by name."""
        registry = PromptRegistry()
        tmpl = PromptLoader.from_string("greeting", "Hello {{ name }}!")
        registry.register(tmpl)

        result = registry.get("greeting")
        assert result is tmpl

    def test_get_latest_version(self):
        """When multiple versions exist, get() without version returns latest."""
        registry = PromptRegistry()
        v1 = PromptLoader.from_string("greeting", "Hi {{ name }}", version="1.0.0")
        v2 = PromptLoader.from_string("greeting", "Hey {{ name }}", version="2.0.0")
        registry.register(v1)
        registry.register(v2)

        result = registry.get("greeting")
        assert result is v2

    def test_get_specific_version(self):
        """Retrieve a specific version of a template."""
        registry = PromptRegistry()
        v1 = PromptLoader.from_string("greeting", "Hi {{ name }}", version="1.0.0")
        v2 = PromptLoader.from_string("greeting", "Hey {{ name }}", version="2.0.0")
        registry.register(v1)
        registry.register(v2)

        result = registry.get("greeting", version="1.0.0")
        assert result is v1

    def test_get_nonexistent_raises(self):
        """Getting a template that doesn't exist raises PromptNotFoundError."""
        registry = PromptRegistry()
        with pytest.raises(PromptNotFoundError):
            registry.get("nonexistent")

    def test_has_and_contains(self):
        """has() and __contains__ return True for registered templates."""
        registry = PromptRegistry()
        tmpl = PromptLoader.from_string("greeting", "Hello")
        registry.register(tmpl)

        assert registry.has("greeting") is True
        assert "greeting" in registry
        assert registry.has("unknown") is False
        assert "unknown" not in registry

    def test_list_templates(self):
        """list_templates() returns PromptInfo for all registered templates."""
        registry = PromptRegistry()
        registry.register(PromptLoader.from_string("a", "Template A"))
        registry.register(PromptLoader.from_string("b", "Template B"))

        infos = registry.list_templates()
        names = {info.name for info in infos}
        assert names == {"a", "b"}

    def test_len(self):
        """__len__ returns the number of registered templates."""
        registry = PromptRegistry()
        assert len(registry) == 0
        registry.register(PromptLoader.from_string("a", "A"))
        assert len(registry) == 1

    def test_clear(self):
        """clear() removes all templates."""
        registry = PromptRegistry()
        registry.register(PromptLoader.from_string("a", "A"))
        registry.clear()
        assert len(registry) == 0
        assert registry.has("a") is False


# ---------------------------------------------------------------------------
# Template rendering and variable injection
# ---------------------------------------------------------------------------

class TestTemplateRendering:
    def test_render_with_variables(self):
        """Render a template with variable injection."""
        tmpl = PromptLoader.from_string("test", "Hello {{ name }}, welcome to {{ place }}!")
        rendered = tmpl.render(name="Alice", place="Wonderland")
        assert rendered == "Hello Alice, welcome to Wonderland!"

    def test_render_with_complex_data(self):
        """Render a template with list iteration."""
        tmpl = PromptLoader.from_string(
            "list_test",
            "{% for item in items %}- {{ item }}\n{% endfor %}",
        )
        rendered = tmpl.render(items=["apple", "banana", "cherry"])
        assert "- apple" in rendered
        assert "- cherry" in rendered


# ---------------------------------------------------------------------------
# register_desk_prompts from disk
# ---------------------------------------------------------------------------

class TestRegisterDeskPrompts:
    def test_loads_templates_from_default_directory(self):
        """register_desk_prompts loads .j2 files from the templates directory."""
        registry = register_desk_prompts()
        # The templates dir should contain files like knowledge_context.j2
        assert len(registry) > 0
        assert registry.has("knowledge_context")

    def test_loads_known_templates(self):
        """Specific expected templates should be loaded."""
        registry = register_desk_prompts()
        expected = [
            "knowledge_context",
            "user_context",
            "available_tools",
            "feedback_context",
        ]
        for name in expected:
            assert registry.has(name), f"Expected template '{name}' not found"

    def test_custom_directory(self, tmp_path: Path):
        """register_desk_prompts can load from a custom directory."""
        (tmp_path / "my_prompt.j2").write_text("Custom prompt: {{ value }}")
        registry = register_desk_prompts(prompts_dir=tmp_path)

        assert registry.has("my_prompt")
        tmpl = registry.get("my_prompt")
        rendered = tmpl.render(value="test")
        assert rendered == "Custom prompt: test"

    def test_empty_directory(self, tmp_path: Path):
        """register_desk_prompts from an empty directory returns empty registry."""
        registry = register_desk_prompts(prompts_dir=tmp_path)
        assert len(registry) == 0
