# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Prompt template admin REST API -- list, view, and override prompt templates."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from jinja2 import BaseLoader, Environment, TemplateSyntaxError, Undefined, UndefinedError
from pydantic import BaseModel

from flydesk.api.deps import get_settings_repo
from flydesk.rbac.guards import AdminSettings
from flydesk.settings.repository import SettingsRepository

_logger = logging.getLogger(__name__)

router = APIRouter(tags=["prompts"])

# Directory where the built-in .j2 templates reside
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "prompts" / "templates"

_PROMPT_CATEGORY = "prompt_override"


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

Repo = Annotated[SettingsRepository, Depends(get_settings_repo)]


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class TemplateInfo(BaseModel):
    """Summary of a prompt template."""

    name: str
    has_override: bool = False


class TemplateDetail(BaseModel):
    """Full template content."""

    name: str
    source: str
    has_override: bool = False


class UpdateTemplateRequest(BaseModel):
    """Body for PUT /api/admin/prompts/templates/{name}."""

    source: str


class PreviewTemplateRequest(BaseModel):
    """Body for POST /api/admin/prompts/templates/{name}/preview."""

    source: str | None = None


# ---------------------------------------------------------------------------
# Sample context for template preview rendering
# ---------------------------------------------------------------------------

_SAMPLE_CONTEXT: dict[str, object] = {
    # identity_custom
    "agent_name": "Ember",
    "company_name": "Acme Corporation",
    "personality": "warm, professional, knowledgeable",
    "tone": "friendly yet precise",
    "behavior_rules": [
        "Never share internal credentials or API keys with users.",
        "Always confirm destructive operations before executing them.",
        "Escalate requests outside your scope to a human operator.",
    ],
    "custom_instructions": "Focus on operational efficiency. Prioritize actionable answers over lengthy explanations.",
    "language": "en",
    # user_context
    "user_name": "Jane Doe",
    "user_roles": ["admin", "operator"],
    "user_department": "Engineering",
    "user_title": "Platform Engineer",
    # available_tools
    "tool_summaries": [
        {"name": "search_knowledge", "risk_level": "read", "description": "Search the knowledge base for documents and articles."},
        {"name": "list_catalog_systems", "risk_level": "read", "description": "List all registered systems in the service catalog."},
        {"name": "list_system_endpoints", "risk_level": "read", "description": "List API endpoints for a given system."},
        {"name": "query_audit_log", "risk_level": "read", "description": "Query the audit log for recent events and changes."},
        {"name": "get_platform_status", "risk_level": "read", "description": "Get current platform health and component status."},
        {"name": "create_ticket", "risk_level": "low_write", "description": "Create a support ticket in the ticketing system."},
        {"name": "delete_user_account", "risk_level": "destructive", "description": "Permanently delete a user account and all associated data."},
    ],
    # knowledge_context
    "knowledge_context": (
        "## Employee Handbook - Leave Policy\n"
        "Employees are entitled to 20 days of annual leave per calendar year. "
        "Unused leave may be carried over up to a maximum of 5 days.\n\n"
        "## IT Security Policy\n"
        "All production access requires MFA. SSH keys must be rotated every 90 days."
    ),
    # file_context
    "file_context": "report_q4_2025.pdf (45 KB) — Quarterly financial report\narchitecture_diagram.png (120 KB) — System architecture overview",
    # conversation_history
    "conversation_summary": "The user asked about the company leave policy and then inquired about available API endpoints for the CRM system.",
    # relevant_processes
    "processes": [
        {
            "name": "Employee Onboarding",
            "description": "Standard process for onboarding new employees into company systems.",
            "steps": [
                {"description": "Create user account in IAM", "endpoint_id": "iam_create_user"},
                {"description": "Assign default role permissions", "endpoint_id": "iam_assign_roles"},
                {"description": "Send welcome email with credentials", "endpoint_id": None},
            ],
        },
        {
            "name": "Incident Response",
            "description": "Steps to handle a production incident.",
            "steps": [
                {"description": "Acknowledge the alert and assess severity", "endpoint_id": None},
                {"description": "Query audit log for recent changes", "endpoint_id": "query_audit_log"},
                {"description": "Notify on-call team via Slack", "endpoint_id": "slack_notify"},
            ],
        },
    ],
}

# Jinja2 environment for preview rendering (string-based, no file loader).
# PreviewUndefined renders missing variables as «name» instead of raising.
_PreviewUndefined = type(
    "PreviewUndefined",
    (Undefined,),
    {
        "__str__": lambda self: f"\u00ab{self._undefined_name}\u00bb",
        "__iter__": lambda self: iter([]),
        "__bool__": lambda self: False,
    },
)
_jinja_env = Environment(loader=BaseLoader(), undefined=_PreviewUndefined)


# ---------------------------------------------------------------------------
# Endpoints -- all guarded by AdminSettings
# ---------------------------------------------------------------------------


@router.get("/api/admin/prompts/templates", dependencies=[AdminSettings])
async def list_templates(repo: Repo) -> list[dict]:
    """List all .j2 template files from the templates directory."""
    templates: list[dict] = []

    # Get all overrides from DB to flag which templates have been customized
    overrides = await repo.get_all_app_settings(category=_PROMPT_CATEGORY)

    if _TEMPLATES_DIR.exists():
        for f in sorted(_TEMPLATES_DIR.glob("*.j2")):
            override_key = f"prompt:{f.stem}"
            # Empty string override means "reset to default", not a real override
            has_override = override_key in overrides and bool(overrides[override_key])
            templates.append({
                "name": f.stem,
                "has_override": has_override,
            })

    return templates


@router.get("/api/admin/prompts/templates/{name}", dependencies=[AdminSettings])
async def get_template(name: str, repo: Repo) -> dict:
    """Read template content. Returns DB override if one exists, otherwise the file content."""
    # Check for DB override first
    override_key = f"prompt:{name}"
    override = await repo.get_app_setting(override_key)

    template_file = _TEMPLATES_DIR / f"{name}.j2"
    if not template_file.exists():
        raise HTTPException(
            status_code=404, detail=f"Template '{name}' not found"
        )

    if override is not None and override != "":
        return {
            "name": name,
            "source": override,
            "has_override": True,
        }

    source = template_file.read_text(encoding="utf-8")
    return {
        "name": name,
        "source": source,
        "has_override": False,
    }


@router.put("/api/admin/prompts/templates/{name}", dependencies=[AdminSettings])
async def update_template(name: str, body: UpdateTemplateRequest, repo: Repo) -> dict:
    """Store a prompt override in the DB via the settings repository."""
    template_file = _TEMPLATES_DIR / f"{name}.j2"
    if not template_file.exists():
        raise HTTPException(
            status_code=404, detail=f"Template '{name}' not found"
        )

    override_key = f"prompt:{name}"
    await repo.set_app_setting(override_key, body.source, category=_PROMPT_CATEGORY)

    return {
        "name": name,
        "source": body.source,
        "has_override": True,
    }


@router.delete("/api/admin/prompts/templates/{name}/override", dependencies=[AdminSettings])
async def delete_template_override(name: str, repo: Repo) -> dict:
    """Remove a prompt override, reverting to the built-in template."""
    template_file = _TEMPLATES_DIR / f"{name}.j2"
    if not template_file.exists():
        raise HTTPException(
            status_code=404, detail=f"Template '{name}' not found"
        )

    override_key = f"prompt:{name}"
    # Set to empty string effectively removes it; we use set_app_setting
    # to overwrite. A proper delete would be better but we reuse the settings repo.
    override = await repo.get_app_setting(override_key)
    if override is None:
        return {
            "name": name,
            "source": template_file.read_text(encoding="utf-8"),
            "has_override": False,
        }

    # Clear the override by setting to empty -- on next read the file content is returned
    # Actually, just set it to the original file content to effectively "reset"
    await repo.set_app_setting(override_key, "", category=_PROMPT_CATEGORY)

    source = template_file.read_text(encoding="utf-8")
    return {
        "name": name,
        "source": source,
        "has_override": False,
    }


@router.post("/api/admin/prompts/templates/{name}/preview", dependencies=[AdminSettings])
async def preview_template(name: str, body: PreviewTemplateRequest, repo: Repo) -> dict:
    """Render a Jinja2 template with sample context data for preview.

    If ``body.source`` is provided, renders that source string directly.
    Otherwise, renders the saved template (override or default file).
    """
    template_file = _TEMPLATES_DIR / f"{name}.j2"
    if not template_file.exists():
        raise HTTPException(
            status_code=404, detail=f"Template '{name}' not found"
        )

    # Determine the source to render
    if body.source is not None:
        source = body.source
    else:
        override_key = f"prompt:{name}"
        override = await repo.get_app_setting(override_key)
        if override is not None and override != "":
            source = override
        else:
            source = template_file.read_text(encoding="utf-8")

    # Render with sample context
    try:
        template = _jinja_env.from_string(source)
        rendered = template.render(**_SAMPLE_CONTEXT)
    except TemplateSyntaxError as exc:
        return {
            "name": name,
            "rendered": "",
            "error": f"Jinja2 syntax error at line {exc.lineno}: {exc.message}",
        }
    except UndefinedError as exc:
        return {
            "name": name,
            "rendered": "",
            "error": f"Undefined variable: {exc}",
        }
    except Exception as exc:
        _logger.warning("Template preview render failed for %s: %s", name, exc)
        return {
            "name": name,
            "rendered": "",
            "error": f"Render error: {exc}",
        }

    return {
        "name": name,
        "rendered": rendered,
        "error": None,
    }
