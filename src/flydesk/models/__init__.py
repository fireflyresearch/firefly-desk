# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""SQLAlchemy ORM models for Firefly Desk."""

from flydesk.models.audit import AuditEventRow
from flydesk.models.base import Base
from flydesk.models.catalog import CredentialRow, ExternalSystemRow, ServiceEndpointRow
from flydesk.models.conversation import ConversationRow, MessageRow
from flydesk.models.export import ExportRow, ExportTemplateRow
from flydesk.models.file_upload import FileUploadRow
from flydesk.models.knowledge import EntityRow, RelationRow
from flydesk.models.knowledge_base import DocumentChunkRow, KnowledgeDocumentRow
from flydesk.models.llm import LLMProviderRow
from flydesk.models.oidc import OIDCProviderRow
from flydesk.models.role import RoleRow
from flydesk.models.skill import SkillRow
from flydesk.models.user_settings import AppSettingRow, UserSettingRow

__all__ = [
    "AppSettingRow",
    "AuditEventRow",
    "Base",
    "ConversationRow",
    "CredentialRow",
    "DocumentChunkRow",
    "EntityRow",
    "ExportRow",
    "ExportTemplateRow",
    "ExternalSystemRow",
    "FileUploadRow",
    "KnowledgeDocumentRow",
    "LLMProviderRow",
    "MessageRow",
    "OIDCProviderRow",
    "RelationRow",
    "RoleRow",
    "ServiceEndpointRow",
    "SkillRow",
    "UserSettingRow",
]
